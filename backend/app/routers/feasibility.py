from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import feasibility, solver, schemas

router = APIRouter(prefix="/api/feasibility", tags=["feasibility"])


@router.get("/page1")
def page1(db: Session = Depends(get_db)):
    print("[api] GET /feasibility/page1")
    return feasibility.page1_bundles(feasibility.get_context(db))


@router.get("/page2")
def page2(db: Session = Depends(get_db)):
    print("[api] GET /feasibility/page2")
    return feasibility.page2_transports(feasibility.get_context(db))


@router.get("/page3")
def page3(db: Session = Depends(get_db)):
    print("[api] GET /feasibility/page3")
    return feasibility.page3_locations(feasibility.get_context(db))


@router.get("/page4")
def page4(db: Session = Depends(get_db)):
    print("[api] GET /feasibility/page4")
    return feasibility.page4_support(feasibility.get_context(db))


@router.post("/page5")
def page5(payload: schemas.SolveRequest, db: Session = Depends(get_db)):
    print(f"[api] POST /feasibility/page5 daily_cap={payload.daily_cap} quotas={payload.quotas}")
    return solver.solve_daily_cap(db, payload.daily_cap, payload.quotas)
