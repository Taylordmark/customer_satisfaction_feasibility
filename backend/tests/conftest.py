"""
Pytest fixtures for the backend test suite.

IMPORTANT: app.database reads DB_PATH from the environment at *import time*
(engine = create_engine(f"sqlite:///{DB_PATH}") is a module-level statement),
so DB_PATH must be set before `app.*` is imported for the first time anywhere
in the process. That has to happen here, at the top of conftest.py, before
this module (or any test module) imports anything from `app`.
"""
import os
import sys
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="feasibility_test_")
os.environ.setdefault("DB_PATH", os.path.join(_TMP_DIR, "test.db"))

# Make sure `backend/` (the parent of this tests/ dir) is importable as the
# `app` package regardless of the cwd pytest was invoked from.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest  # noqa: E402

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402,F401 -- registers models with Base
from app.seed import seed_if_empty  # noqa: E402

Base.metadata.create_all(bind=engine)


def _reset_db():
    """Wipe every table and reseed the canonical example dataset, so each
    test starts from the same known-good state regardless of what earlier
    tests mutated (including rows written directly via SQLAlchemy, bypassing
    schema validation, to simulate legacy/bad data)."""
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()

    session = SessionLocal()
    try:
        seed_if_empty(session)
    finally:
        session.close()


@pytest.fixture()
def db():
    """A fresh, seeded DB session for a single test."""
    _reset_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """A TestClient against the real FastAPI app, backed by the same
    freshly-seeded database as the `db` fixture (same sqlite file)."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c
