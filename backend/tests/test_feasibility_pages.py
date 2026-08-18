"""
Phase 7 (backend half) — pages 3/4 agree with page 5: out-of-service assets
and refuelers are annotated with "available" but not excluded from the
listings, while feasible/needs_support/unreachable verdicts are computed
from available capability only. Page 3 also gains "partial" stock state.
"""
from app import models, feasibility


def test_page3_capable_assets_have_available_flag(db):
    ctx = feasibility.get_context(db)
    p3 = feasibility.page3_locations(ctx)
    found_any = False
    for cust in p3:
        for pkg in cust["packages"]:
            for wh in pkg["warehouses"]:
                for asset in wh["capable_assets"]:
                    assert "available" in asset
                    found_any = True
    assert found_any, "expected at least one capable_assets entry in the seeded dataset"


def test_page3_out_of_service_asset_excluded_from_feasible_but_still_listed(db):
    """C16's bundle is K1/K2, servable from W1 via Air-1/Air-2. Mark every
    asset at W1 out of service: W1/K1 (and K2) should no longer be
    'feasible' for C16 (no *available* capable asset), but the assets must
    still be listed (grayed out) in capable_assets."""
    for a in db.query(models.Asset).filter_by(home_warehouse_id="W1").all():
        a.available = False
    db.commit()

    ctx = feasibility.get_context(db)
    p3 = feasibility.page3_locations(ctx)
    c16 = next(c for c in p3 if c["customer_id"] == "C16")
    for pkg in c16["packages"]:
        w1 = next((w for w in pkg["warehouses"] if w["warehouse_id"] == "W1"), None)
        if w1 is None:
            continue
        assert w1["capable_assets"], "out-of-service assets should still be listed"
        assert all(not a["available"] for a in w1["capable_assets"])
        assert w1["feasible"] is False, "no available asset -- W1 must not read feasible for C16"


def test_page3_partial_when_stock_below_qty_needed(db):
    """C16 needs 2x K1 (or 2x K2). Set W1's K1 stock to 1 (< needed) while
    keeping an available capable asset -- expect partial, not feasible."""
    inv = db.query(models.WarehouseInventory).filter_by(warehouse_id="W1", package_type_id="K1").first()
    inv.qty = 1
    db.commit()

    ctx = feasibility.get_context(db)
    p3 = feasibility.page3_locations(ctx)
    c16 = next(c for c in p3 if c["customer_id"] == "C16")
    k1_pkg = next(p for p in c16["packages"] if p["package_type_id"] == "K1")
    w1 = next(w for w in k1_pkg["warehouses"] if w["warehouse_id"] == "W1")
    assert w1["stock"] == 1
    assert w1["feasible"] is False
    assert w1["partial"] is True


def test_page3_feasible_requires_full_stock(db):
    """Sanity check the positive case: full stock + available asset -> feasible."""
    ctx = feasibility.get_context(db)
    p3 = feasibility.page3_locations(ctx)
    c16 = next(c for c in p3 if c["customer_id"] == "C16")
    assert c16["fully_feasible"] is True


def test_page4_assets_and_refuelers_have_available_flag(db):
    ctx = feasibility.get_context(db)
    p4 = feasibility.page4_support(ctx)
    seen_direct = seen_supported = seen_refueler = False
    for cust in p4["per_customer"]:
        for a in cust["direct_assets"]:
            assert "available" in a
            seen_direct = True
        for a in cust["supported_assets"]:
            assert "available" in a
            seen_supported = True
            for f in a["refuelers"]:
                assert "available" in f
                seen_refueler = True
    assert seen_direct
    # supported_assets/refuelers may or may not be present depending on the
    # seeded topology -- only assert the shape if we actually saw one
    if seen_supported:
        assert seen_refueler


def test_page4_needs_support_and_unreachable_use_only_available_capability(db):
    """Find a customer reachable only directly (no supported_assets) with at
    least one direct asset, mark that asset out of service, and confirm the
    customer becomes 'unreachable' (no available direct asset, no available
    supported asset) even though direct_assets still lists the vehicle."""
    ctx = feasibility.get_context(db)
    p4 = feasibility.page4_support(ctx)
    candidate = next(
        (c for c in p4["per_customer"]
         if len(c["direct_assets"]) == 1 and not c["supported_assets"]),
        None,
    )
    assert candidate is not None, "expected at least one customer with exactly one direct asset and no support path"
    asset_id = candidate["direct_assets"][0]["asset_id"]

    asset = db.get(models.Asset, asset_id)
    asset.available = False
    db.commit()

    ctx2 = feasibility.get_context(db)
    p4b = feasibility.page4_support(ctx2)
    row = next(c for c in p4b["per_customer"] if c["customer_id"] == candidate["customer_id"])
    assert row["direct_assets"], "the out-of-service asset should still be listed"
    assert row["direct_assets"][0]["available"] is False
    assert row["unreachable"] is True
    assert row["needs_support"] is False


def test_page4_supported_needs_available_refueler_too(db):
    """A customer only reachable via a refueler must not read needs_support
    when that refueler is marked out of service (even though the asset
    itself is available)."""
    ctx = feasibility.get_context(db)
    p4 = feasibility.page4_support(ctx)
    candidate = next(
        (c for c in p4["per_customer"]
         if not c["direct_assets"] and c["supported_assets"]),
        None,
    )
    if candidate is None:
        return  # seeded topology has no such customer -- nothing to assert

    row = candidate["supported_assets"][0]
    for f in row["refuelers"]:
        refueler = db.get(models.Refueler, f["refueler_id"])
        refueler.available = False
    db.commit()

    ctx2 = feasibility.get_context(db)
    p4b = feasibility.page4_support(ctx2)
    row2 = next(c for c in p4b["per_customer"] if c["customer_id"] == candidate["customer_id"])
    assert row2["supported_assets"], "the vehicle/refuelers should still be listed"
    assert all(not f["available"] for a in row2["supported_assets"] for f in a["refuelers"]
               if a["asset_id"] == row["asset_id"])
    assert row2["unreachable"] is True
    assert row2["needs_support"] is False
