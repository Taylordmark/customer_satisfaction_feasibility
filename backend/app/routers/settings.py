from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return db.query(models.Settings).first()


@router.put("/", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsBase, db: Session = Depends(get_db)):
    obj = db.query(models.Settings).first()
    for field, value in payload.model_dump().items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj
