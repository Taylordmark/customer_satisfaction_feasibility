"""
Phase 0 regression harness — direct ports of the five audit probes
(/private/tmp/.../scratchpad/audit_probe.py). Every test here fails against
the pre-remediation code; Phases 1-4 turn them green one at a time.
"""
from app import models, schemas, solver, feasibility


# ---------------------------------------------------------------------------
# Probe 1 (M1) — aggressive quota must not manufacture cargo-less dispatches
# ---------------------------------------------------------------------------
def test_no_phantom_cargo_under_aggressive_quota(db):
    fob = db.query(models.CustomerType).filter_by(name="FOB").first()
    quotas = [schemas.QuotaInput(customer_type_id=fob.id, target_pct=0.70)]

    res = solver.solve_daily_cap(db, 8, quotas)

    assert res["modes"], "expected the solve to produce mode results"
    for m in res["modes"]:
        empty = [d for d in m["dispatches"] if not d["cargo"]]
        assert not empty, (
            f"mode={m['mode']} has {len(empty)} phantom (cargo-less) dispatch(es): {empty}"
        )


# ---------------------------------------------------------------------------
# Probe 2 (M3) — priority_rank beyond len(customers) must not flip the
# rank_weighted objective weight negative and starve an easy customer.
# ---------------------------------------------------------------------------
def test_rank_overflow_still_satisfiable_at_slack_cap(db):
    c16 = db.get(models.Customer, "C16")  # Hilo Storefront, near W1
    c16.priority_rank = 40  # only 24 customers exist
    db.commit()

    res = solver.solve_daily_cap(db, 30, [])  # slack cap, no quotas

    m = next(m for m in res["modes"] if m["mode"] == "rank_weighted")
    assert m["status"] == "Optimal"
    c16r = next(r for r in m["customers"] if r["customer_id"] == "C16")
    assert c16r["satisfied"], (
        "C16 (trivially servable) should be satisfied under rank_weighted "
        "at a slack cap even with priority_rank far beyond the customer count"
    )


# ---------------------------------------------------------------------------
# Probe 3 (M4) — speed_mph = 0 must not divide-by-zero / 500 the feasibility
# pages or the solve; the affected assets should just be reported unreachable
# with a visible data warning.
# ---------------------------------------------------------------------------
def test_speed_mph_zero_write_rejected(client):
    r = client.put(
        "/api/method-specs/Ground",
        json={"method": "Ground", "speed_mph": 0, "weight_cap": 5000, "vol_cap": 400, "range_mi": 400},
    )
    assert r.status_code == 422


def test_speed_mph_zero_legacy_row_does_not_crash(db):
    spec = db.get(models.MethodSpec, "Ground")
    spec.speed_mph = 0
    db.commit()

    # get_context()/pages must not raise
    ctx = feasibility.get_context(db)
    feasibility.page1_bundles(ctx)
    feasibility.page2_transports(ctx)
    feasibility.page3_locations(ctx)
    feasibility.page4_support(ctx)

    res = solver.solve_daily_cap(db, 8, [])  # solve must not raise either
    assert res["modes"], "solve should still produce results despite the bad spec"

    ground_assets = {a.id for a in db.query(models.Asset).filter_by(method="Ground").all()}
    assert res.get("data_warnings"), "expected data_warnings to name the affected Ground assets"
    warned_text = " ".join(res["data_warnings"])
    assert any(a in warned_text for a in ground_assets), (
        f"data_warnings {res['data_warnings']!r} should name an affected Ground asset"
    )


# ---------------------------------------------------------------------------
# Probe 4 (M2) — zero-weight/zero-volume package must not let a customer be
# reported satisfied with no dispatch ever actually carrying anything.
# ---------------------------------------------------------------------------
def test_zero_weight_package_write_rejected(client):
    r = client.post(
        "/api/package-types/",
        json={"id": "KZ", "name": "Zero-weight", "weight": 0, "volume": 1.0},
    )
    assert r.status_code == 422

    r2 = client.post(
        "/api/package-types/",
        json={"id": "KZ2", "name": "Zero-volume", "weight": 1.0, "volume": 0},
    )
    assert r2.status_code == 422


def test_zero_weight_package_legacy_row_no_free_satisfaction(db):
    k1 = db.get(models.PackageType, "K1")
    k1.weight = 0
    k1.volume = 0
    db.commit()

    res = solver.solve_daily_cap(db, 1, [])  # cap of ONE mission

    for m in res["modes"]:
        dispatched_to = {d["customer_id"] for d in m["dispatches"]}
        satisfied_without_dispatch = [
            r["customer_id"] for r in m["customers"] if r["satisfied"] and r["customer_id"] not in dispatched_to
        ]
        assert not satisfied_without_dispatch, (
            f"mode={m['mode']}: customers satisfied with no dispatch: {satisfied_without_dispatch}"
        )


# ---------------------------------------------------------------------------
# Probe 5 (M5) — two source-warehouse pins for the same customer must be a
# reported conflict, not a silent last-write-wins.
# ---------------------------------------------------------------------------
def test_duplicate_source_pins_reported_as_conflict(db):
    db.add(models.PlannedMission(customer_id="C16", source_warehouse_id="W1"))
    db.add(models.PlannedMission(customer_id="C16", source_warehouse_id="W2"))
    db.commit()

    res = solver.solve_daily_cap(db, 8, [])

    assert res["pin_conflicts"], "expected a pin conflict for two distinct source-warehouse pins"
    assert res["modes"] == [], "a pin conflict must refuse to solve, not silently pick one pin"
