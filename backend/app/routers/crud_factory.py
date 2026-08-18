import logging
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import create_model
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db

logger = logging.getLogger(__name__)


def _make_partial_schema(create_schema):
    """Build a copy of create_schema with every field made optional
    (default=None), preserving each field's type and constraints
    (gt/ge/le, etc.) so PATCH bodies are validated the same way POST/PUT
    bodies are — just with everything optional. Combined with
    `exclude_unset=True` on read, this lets callers send any subset of
    fields.
    """
    fields = {}
    for name, field_info in create_schema.model_fields.items():
        new_field = deepcopy(field_info)
        new_field.default = None
        new_field.annotation = Optional[field_info.annotation]
        fields[name] = (new_field.annotation, new_field)
    return create_model(f"{create_schema.__name__}Partial", **fields)


def _translate_integrity_error(e: IntegrityError, entity_name: str, action: str) -> HTTPException:
    """Never surface raw driver text to the client — log it, and return a
    generic, entity-scoped message translated from the constraint that
    tripped."""
    orig_text = str(getattr(e, "orig", None) or e)
    logger.error("IntegrityError while trying to %s %s: %s", action, entity_name, orig_text)
    upper = orig_text.upper()
    if "FOREIGN KEY" in upper:
        if action == "delete":
            return HTTPException(400, f"{entity_name} is still referenced by other records and can't be deleted.")
        return HTTPException(400, f"{entity_name} references a record that doesn't exist — check the linked IDs.")
    if "UNIQUE" in upper:
        return HTTPException(400, f"{entity_name} already exists for that combination.")
    if action == "delete":
        return HTTPException(400, f"Could not delete {entity_name}.")
    return HTTPException(400, f"Could not save {entity_name}.")


def make_crud_router(*, prefix, tag, model, create_schema, out_schema, id_type=str):
    router = APIRouter(prefix=prefix, tags=[tag])
    partial_schema = _make_partial_schema(create_schema)

    def cast_id(item_id: str):
        return int(item_id) if id_type is int else item_id

    @router.get("/", response_model=list[out_schema])
    def list_all(db: Session = Depends(get_db)):
        return db.query(model).all()

    @router.get("/{item_id}", response_model=out_schema)
    def get_one(item_id: str, db: Session = Depends(get_db)):
        obj = db.get(model, cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        return obj

    @router.post("/", response_model=out_schema, status_code=201)
    def create(payload: create_schema, db: Session = Depends(get_db)):
        obj = model(**payload.model_dump())
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _translate_integrity_error(e, model.__name__, "create")
        db.refresh(obj)
        return obj

    @router.put("/{item_id}", response_model=out_schema)
    def update(item_id: str, payload: create_schema, db: Session = Depends(get_db)):
        obj = db.get(model, cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        for field, value in payload.model_dump().items():
            setattr(obj, field, value)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _translate_integrity_error(e, model.__name__, "update")
        db.refresh(obj)
        return obj

    @router.patch("/{item_id}", response_model=out_schema)
    def patch(item_id: str, payload: partial_schema, db: Session = Depends(get_db)):
        obj = db.get(model, cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _translate_integrity_error(e, model.__name__, "update")
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete(item_id: str, db: Session = Depends(get_db)):
        obj = db.get(model, cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        try:
            db.delete(obj)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _translate_integrity_error(e, model.__name__, "delete")
        return None

    return router
