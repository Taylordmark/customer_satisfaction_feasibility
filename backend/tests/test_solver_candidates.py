"""
Phase 1 — candidate pruning (M1a) and LP variable naming (M10).
"""
from app import models, feasibility, solver


def test_asset_barred_from_every_bundle_option_is_pruned(db):
    """C1 (Okinawa FOB) only wants K3 or K5. Air assets are barred from both
    (see seed data), so no Air asset should ever appear as a z-candidate for
    C1, even though Air-1 physically reaches Okinawa from W1."""
    ctx = feasibility.get_context(db)
    eligible = [c for c in ctx["customers"] if ctx["bundles"].get(c) and ctx["customers"][c].included]
    z_candidates, _p_candidates = solver._build_candidates(ctx, eligible)

    air_assets = {a for a in ctx["assets"] if ctx["assets"][a].method == "Air"}
    offenders = [(a, c) for (a, c) in z_candidates if c == "C1" and a in air_assets]
    assert not offenders, f"Air assets should be pruned as candidates for C1 (K3/K5 only): {offenders}"


def test_pin_conflict_distinguishes_cant_carry_from_cant_reach(db):
    """Bar Air-2's vehicle type from both of C16's bundle options, then pin
    Air-2 to C16. Air-1 (based at W1 like Air-2, but a different vehicle
    type and untouched by the restriction) still reaches C16 within the
    cycle, so C16 is NOT globally unreachable -- the pin failure is
    specifically that Air-2 can't carry anything C16 wants, and the
    conflict message must say so, not claim Air-2 can't reach C16 (which
    it physically can)."""
    air2_vtype = db.get(models.Asset, "Air-2").vehicle_type
    db.add(models.VehicleTypeRestriction(vehicle_type=air2_vtype, package_type_id="K1"))
    db.add(models.VehicleTypeRestriction(vehicle_type=air2_vtype, package_type_id="K2"))
    db.add(models.PlannedMission(customer_id="C16", asset_id="Air-2"))
    db.commit()

    res = solver.solve_daily_cap(db, 8, [])
    assert res["pin_conflicts"], "expected a pin conflict"
    joined = " ".join(res["pin_conflicts"])
    assert "carry" in joined.lower(), f"expected a carrying-capability conflict, got: {res['pin_conflicts']}"


def test_entity_ids_with_spaces_and_punctuation_do_not_collide(db):
    """LP variable names must never embed raw entity IDs (PuLP sanitizes
    special characters in variable names, which can silently collide two
    distinct entities into the same LP variable). Create a customer and an
    asset whose IDs contain spaces/punctuation that would collide after
    PuLP's sanitization if names were built from the IDs directly, and
    confirm the solve still runs and reports a sane result."""
    db.add(models.Customer(id="C spaced-1", label="Spaced Customer", lat=21.0, lon=-157.0,
                            priority_rank=2, included=True))
    db.add(models.CustomerBundleItem(customer_id="C spaced-1", package_type_id="K1", qty_needed=1))
    # Another id that sanitizes to the exact same token PuLP would produce
    # for "C spaced-1" if underscores were substituted for spaces/dashes.
    db.add(models.Customer(id="C_spaced_1", label="Underscored Customer", lat=21.1, lon=-157.1,
                            priority_rank=3, included=True))
    db.add(models.CustomerBundleItem(customer_id="C_spaced_1", package_type_id="K1", qty_needed=1))
    db.commit()

    res = solver.solve_daily_cap(db, 30, [])
    assert res["modes"], "solve should succeed despite colliding-looking IDs"
    for m in res["modes"]:
        assert m["status"] in ("Optimal",), f"mode {m['mode']} unexpectedly {m['status']}"
        ids_seen = {r["customer_id"] for r in m["customers"]}
        assert "C spaced-1" in ids_seen
        assert "C_spaced_1" in ids_seen
