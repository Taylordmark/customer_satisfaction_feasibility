import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return db.query(models.Settings).first()


@router.put("/", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsBase, db: Session = Depends(get_db)):
    obj = db.query(models.Settings).first()
    if obj is None:
        # Should not happen in practice — the startup lifespan guarantees a
        # settings row exists — but guard against it rather than crashing
        # with AttributeError on None if it's ever missing (e.g. manual DB
        # tampering).
        logger.warning("Settings row missing on PUT — creating it from the submitted payload")
        obj = models.Settings(id=1, **payload.model_dump())
        db.add(obj)
    else:
        for field, value in payload.model_dump().items():
            setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj
