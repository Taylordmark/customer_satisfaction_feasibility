from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..database import get_db


def make_crud_router(*, prefix, tag, model, create_schema, out_schema, id_type=str):
    router = APIRouter(prefix=prefix, tags=[tag])

    def cast_id(item_id: str):
        return int(item_id) if id_type is int else item_id

    @router.get("/", response_model=list[out_schema])
    def list_all(db: Session = Depends(get_db)):
        return db.query(model).all()

    @router.get("/{item_id}", response_model=out_schema)
    def get_one(item_id: str, db: Session = Depends(get_db)):
        obj = db.query(model).get(cast_id(item_id))
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
            raise HTTPException(400, f"Could not create {model.__name__}: {e.orig}")
        db.refresh(obj)
        return obj

    @router.put("/{item_id}", response_model=out_schema)
    def update(item_id: str, payload: create_schema, db: Session = Depends(get_db)):
        obj = db.query(model).get(cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        for field, value in payload.model_dump().items():
            setattr(obj, field, value)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(400, f"Could not update {model.__name__}: {e.orig}")
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete(item_id: str, db: Session = Depends(get_db)):
        obj = db.query(model).get(cast_id(item_id))
        if obj is None:
            raise HTTPException(404, f"{model.__name__} '{item_id}' not found")
        try:
            db.delete(obj)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(400, f"Could not delete {model.__name__} — likely referenced elsewhere: {e.orig}")
        return None

    return router
