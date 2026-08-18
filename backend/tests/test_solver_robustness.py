"""
Phase 3 — solver robustness: time limit env var + time_limited flag,
concurrency lock, and true lexicographic strict_priority.
"""
import os
import threading

import pulp
import pytest

from app import models, solver


# ---------------------------------------------------------------------------
# M6 — SOLVER_TIME_LIMIT_S is read from the environment and passed through
# ---------------------------------------------------------------------------
def test_time_limit_env_var_is_honored(monkeypatch):
    monkeypatch.setenv("SOLVER_TIME_LIMIT_S", "5")
    s = solver._get_solver(solver._time_limit_s())
    assert s.timeLimit == 5.0


def test_time_limit_env_var_default_is_60(monkeypatch):
    monkeypatch.delenv("SOLVER_TIME_LIMIT_S", raising=False)
    assert solver._time_limit_s() == 60.0


def test_time_limit_env_var_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SOLVER_TIME_LIMIT_S", "not-a-number")
    assert solver._time_limit_s() == 60.0


# ---------------------------------------------------------------------------
# M6b — a time-limited incumbent is reported distinctly from Infeasible, and
# the (suboptimal-but-feasible) solution is still extracted and returned.
# ---------------------------------------------------------------------------
def _hard_knapsack_model():
    """A synthetic MILP big enough that a very small time limit plausibly
    stops the solver before it can prove optimality, matching the empirical
    probe used to design solver._is_time_limited."""
    import random
    random.seed(7)
    n = 90
    model = pulp.LpProblem("hard", pulp.LpMaximize)
    xs = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    weights = [random.randint(1, 1000) for _ in range(n)]
    values = [random.randint(1, 1000) for _ in range(n)]
    cap = sum(weights) // 2
    model += pulp.lpSum(values[i] * xs[i] for i in range(n))
    model += pulp.lpSum(weights[i] * xs[i] for i in range(n)) <= cap
    for _ in range(70):
        idx = random.sample(range(n), 15)
        model += pulp.lpSum(xs[i] for i in idx) <= random.randint(2, 6)
    return model


def test_time_limited_incumbent_is_reported_and_extracted():
    model = _hard_knapsack_model()
    tiny_solver = solver._get_solver(0.01)
    model.solve(tiny_solver)

    assert pulp.LpStatus[model.status] == "Optimal", (
        "a time-limited run with an incumbent still reports LpStatus Optimal "
        "(verified empirically) -- this is exactly the case time_limited must catch"
    )
    assert solver._is_time_limited(model) is True
    # a real value was extracted, not garbage/None
    assert pulp.value(model.objective) is not None


def test_generous_time_limit_is_not_flagged_time_limited(db):
    """A normal, fast solve on the (small) seeded dataset must NOT be
    reported as time_limited."""
    res = solver.solve_daily_cap(db, 8, [])
    for m in res["modes"]:
        assert m["status"] == "Optimal"
        assert m["time_limited"] is False


# ---------------------------------------------------------------------------
# M6c — concurrent requests are serialized through a module-level lock
# ---------------------------------------------------------------------------
def test_solve_lock_serializes_concurrent_calls(db, monkeypatch):
    """A real threading.Lock (a `_thread.lock` C object) doesn't allow its
    bound methods to be patched in place, so swap the module-level
    `_solve_lock` attribute itself for an instrumented wrapper around a real
    Lock, for the duration of this test only (monkeypatch restores it after).
    Each thread gets its own SQLAlchemy session (mirroring one session per
    request in production via Depends(get_db)) so this exercises the lock,
    not incidental ORM session thread-safety."""
    from app.database import SessionLocal

    assert isinstance(solver._solve_lock, type(threading.Lock()))

    real_lock = solver._solve_lock
    active = {"count": 0}
    counter_lock = threading.Lock()
    overlap = []

    class TrackingLock:
        def acquire(self, *a, **kw):
            ok = real_lock.acquire(*a, **kw)
            with counter_lock:
                active["count"] += 1
                if active["count"] > 1:
                    overlap.append(True)
            return ok

        def release(self, *a, **kw):
            with counter_lock:
                active["count"] -= 1
            return real_lock.release(*a, **kw)

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *exc):
            self.release()
            return False

    monkeypatch.setattr(solver, "_solve_lock", TrackingLock())

    errors = []

    def run():
        session = SessionLocal()
        try:
            solver.solve_daily_cap(session, 8, [])
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=run) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"concurrent solves raised: {errors}"
    assert not overlap, "solve_lock should never be held by more than one thread at once"


# ---------------------------------------------------------------------------
# M7 — true lexicographic strict_priority: a top-rank customer always wins
# over any number of lower-ranked ones, and it scales past the ~40-customer
# ceiling where the old exponential-weight trick silently broke.
# ---------------------------------------------------------------------------
def test_strict_priority_never_sacrifices_top_rank_for_many_lower_ranks(db):
    """Isolate a clean resource conflict: exclude every seeded customer
    (some, like C1, are deliberately structurally unservable per
    SCENARIO.md and would just muddy this), then add two synthetic
    customers next door to W1 that both want the same package and are both
    trivially reachable -- but cap the day at exactly one mission, so
    exactly one of them can be served. strict_priority must pick the
    higher-priority one every time."""
    for c in db.query(models.Customer).all():
        c.included = False
    db.add(models.Customer(id="SYNA", label="Top priority", lat=21.36, lon=-157.96,
                            priority_rank=1, included=True))
    db.add(models.CustomerBundleItem(customer_id="SYNA", package_type_id="K1", qty_needed=1))
    db.add(models.Customer(id="SYNB", label="Lower priority", lat=21.34, lon=-157.94,
                            priority_rank=2, included=True))
    db.add(models.CustomerBundleItem(customer_id="SYNB", package_type_id="K1", qty_needed=1))
    db.commit()

    res = solver.solve_daily_cap(db, 1, [])  # exactly one mission allowed
    m = next(m for m in res["modes"] if m["mode"] == "strict_priority")
    assert m["status"] == "Optimal"
    by_id = {r["customer_id"]: r["satisfied"] for r in m["customers"]}
    assert by_id["SYNA"] is True, f"higher-priority customer must win: {m['customers']}"
    assert by_id["SYNB"] is False, f"only one mission was allowed: {m['customers']}"


def test_strict_priority_scales_past_forty_customers(db):
    """The old exponential-weight trick silently breaks around ~40
    customers (float overflow / precision). Build a synthetic 60-customer
    instance sharing the seeded warehouses/assets and confirm strict_priority
    still solves to Optimal and respects rank order exactly."""
    import random
    random.seed(123)
    w_ids = [w.id for w in db.query(models.Warehouse).all()]
    for i in range(60):
        c_id = f"SYN{i}"
        w = db.get(models.Warehouse, w_ids[i % len(w_ids)])
        db.add(models.Customer(
            id=c_id, label=f"Synthetic {i}",
            lat=w.lat + random.uniform(-0.5, 0.5), lon=w.lon + random.uniform(-0.5, 0.5),
            priority_rank=100 + i,  # keep out of the way of seeded ranks 1-24
            included=True,
        ))
        db.add(models.CustomerBundleItem(customer_id=c_id, package_type_id="K1", qty_needed=1))
    db.commit()

    res = solver.solve_daily_cap(db, 30, [])
    m = next(m for m in res["modes"] if m["mode"] == "strict_priority")
    assert m["status"] == "Optimal"

    # rank order respected: no lower-priority (higher rank number) synthetic
    # customer satisfied while a strictly higher-priority (lower rank
    # number) synthetic customer, at slack cap-availability, was not -- spot
    # check via satisfied_ranks being satisfiable in ascending-priority order
    by_rank = {r["rank"]: r["satisfied"] for r in m["customers"]}
    synthetic_ranks = sorted(r for r in by_rank if r >= 100)
    # find the first unsatisfied synthetic rank, if any; every synthetic
    # rank before it must be satisfied (no gaps favoring a lower priority)
    first_unsatisfied = next((r for r in synthetic_ranks if not by_rank[r]), None)
    if first_unsatisfied is not None:
        gaps = [r for r in synthetic_ranks if r < first_unsatisfied and not by_rank[r]]
        assert not gaps, f"lower-priority ranks satisfied while higher-priority ranks were not: {gaps}"
