import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 — ensures models are registered before create_all
from .seed import seed_if_empty
from .routers.entities import all_crud_routers
from .routers.settings import router as settings_router
from .routers.feasibility import router as feasibility_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("creating tables if needed...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        # The settings router and solver both assume exactly one Settings
        # row exists. seed_if_empty creates one on a fresh database, but if
        # the DB already had data (so seeding was skipped) and the row is
        # somehow missing, create it here with the model defaults.
        if db.query(models.Settings).first() is None:
            logger.info("no settings row found — creating one with defaults")
            db.add(models.Settings())
            db.commit()
    finally:
        db.close()
    logger.info("ready")
    yield


app = FastAPI(title="Delivery Feasibility Assessment API", lifespan=lifespan)

_cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
if _cors_origins_env.strip() == "*":
    _allow_origins = ["*"]
else:
    _allow_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


for r in all_crud_routers:
    app.include_router(r)
app.include_router(settings_router)
app.include_router(feasibility_router)
