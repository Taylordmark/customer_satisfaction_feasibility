from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 — ensures models are registered before create_all
from .seed import seed_if_empty
from .routers.entities import all_crud_routers
from .routers.settings import router as settings_router
from .routers.feasibility import router as feasibility_router

app = FastAPI(title="Delivery Feasibility Assessment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    print("[startup] creating tables if needed...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    print("[startup] ready")


@app.get("/api/health")
def health():
    return {"status": "ok"}


for r in all_crud_routers:
    app.include_router(r)
app.include_router(settings_router)
app.include_router(feasibility_router)
