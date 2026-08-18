"""
Phase 2 — Field constraints on write schemas. One 422 assertion per
constrained field/entity named in FIXPLAN. Legacy-row defense-in-depth
(rank_weighted weight floor, speed_mph<=0 handling) is covered by
test_audit_regressions.py and test_solver_robustness.py.
"""
import pytest


@pytest.mark.parametrize("payload", [
    {"method": "X", "speed_mph": -1, "weight_cap": 1, "vol_cap": 1, "range_mi": 1},
    {"method": "X", "speed_mph": 1, "weight_cap": 0, "vol_cap": 1, "range_mi": 1},
    {"method": "X", "speed_mph": 1, "weight_cap": 1, "vol_cap": 0, "range_mi": 1},
    {"method": "X", "speed_mph": 1, "weight_cap": 1, "vol_cap": 1, "range_mi": 0},
])
def test_method_spec_rejects_non_positive_fields(client, payload):
    r = client.post("/api/method-specs/", json=payload)
    assert r.status_code == 422


def test_refueler_rejects_negative_extension_and_range(client):
    r = client.post("/api/refuelers/", json={
        "id": "TZ", "home_warehouse_id": "W1", "extension_mi": -1, "self_range_mi": 100,
    })
    assert r.status_code == 422
    r2 = client.post("/api/refuelers/", json={
        "id": "TZ2", "home_warehouse_id": "W1", "extension_mi": 100, "self_range_mi": -1,
    })
    assert r2.status_code == 422


def test_warehouse_inventory_rejects_negative_qty(client):
    r = client.post("/api/warehouse-inventory/", json={
        "warehouse_id": "W1", "package_type_id": "K1", "qty": -5,
    })
    assert r.status_code == 422


def test_customer_bundle_item_rejects_zero_qty_needed(client):
    r = client.post("/api/customer-bundle-items/", json={
        "customer_id": "C1", "package_type_id": "K1", "qty_needed": 0,
    })
    assert r.status_code == 422


@pytest.mark.parametrize("payload", [
    {"id": "CZ", "label": "Bad rank", "lat": 0, "lon": 0, "priority_rank": 0},
    {"id": "CZ", "label": "Bad lat", "lat": 91, "lon": 0, "priority_rank": 1},
    {"id": "CZ", "label": "Bad lat neg", "lat": -91, "lon": 0, "priority_rank": 1},
    {"id": "CZ", "label": "Bad lon", "lat": 0, "lon": 181, "priority_rank": 1},
    {"id": "CZ", "label": "Bad lon neg", "lat": 0, "lon": -181, "priority_rank": 1},
])
def test_customer_rejects_bad_rank_and_coordinates(client, payload):
    r = client.post("/api/customers/", json=payload)
    assert r.status_code == 422


@pytest.mark.parametrize("payload", [
    {"id": "WZ", "label": "Bad lat", "lat": 91, "lon": 0},
    {"id": "WZ", "label": "Bad lon", "lat": 0, "lon": 181},
])
def test_warehouse_rejects_bad_coordinates(client, payload):
    r = client.post("/api/warehouses/", json=payload)
    assert r.status_code == 422


def test_allocation_policy_rejects_target_pct_out_of_range(client):
    ct = client.post("/api/customer-types/", json={"name": "TestType"}).json()
    r = client.post("/api/allocation-policies/", json={
        "customer_type_id": ct["id"], "target_pct": 0,
    })
    assert r.status_code == 422
    r2 = client.post("/api/allocation-policies/", json={
        "customer_type_id": ct["id"], "target_pct": 1.5,
    })
    assert r2.status_code == 422


def test_solve_request_rejects_non_positive_daily_cap(client):
    r = client.post("/api/feasibility/page5", json={"daily_cap": 0})
    assert r.status_code == 422
    r2 = client.post("/api/feasibility/page5", json={"daily_cap": -3})
    assert r2.status_code == 422


def test_settings_rejects_bad_values(client):
    bad_payloads = [
        {"cycle_hours": 0, "handling_time_hours": 1, "refuel_overhead_hours": 1, "default_daily_cap": 5},
        {"cycle_hours": 24, "handling_time_hours": -1, "refuel_overhead_hours": 1, "default_daily_cap": 5},
        {"cycle_hours": 24, "handling_time_hours": 1, "refuel_overhead_hours": -1, "default_daily_cap": 5},
        {"cycle_hours": 24, "handling_time_hours": 1, "refuel_overhead_hours": 1, "default_daily_cap": 0},
    ]
    for payload in bad_payloads:
        r = client.put("/api/settings/", json=payload)
        assert r.status_code == 422, payload
