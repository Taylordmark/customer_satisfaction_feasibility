from sqlalchemy.orm import Session
from . import models


def seed_if_empty(db: Session):
    if db.query(models.Warehouse).count() > 0:
        print("[seed] database already has data, skipping seed")
        return

    print("[seed] empty database — loading example dataset")

    warehouses = [
        ("W1", "West Hub", 21.35, -157.95),
        ("W2", "South Hub", 13.47, 144.75),
        ("W3", "North Hub", 15.19, 120.56),
        ("W4", "South-West Hub", -12.46, 130.84),
        ("W5", "Far North Hub", 61.22, -149.90),
    ]
    for id_, label, lat, lon in warehouses:
        db.add(models.Warehouse(id=id_, label=label, lat=lat, lon=lon))
    db.flush()

    teams = [
        ("West Hub Transport Control Team", "W1"),
        ("South Hub Transport Control Team", "W2"),
        ("North Hub Transport Control Team", "W3"),
        ("South-West Hub Transport Control Team", "W4"),
        ("Far North Hub Transport Control Team", "W5"),
    ]
    team_id_by_warehouse = {}
    for name, w_id in teams:
        t = models.TransportControlTeam(name=name, warehouse_id=w_id,
                                         description=f"Owns and tasks transport assets based at {w_id}")
        db.add(t)
        db.flush()
        team_id_by_warehouse[w_id] = t.id

    customer_types = ["Storefront", "Warehouse", "FOB", "Distribution Center"]
    type_id_by_name = {}
    for name in customer_types:
        ct = models.CustomerType(name=name)
        db.add(ct)
        db.flush()
        type_id_by_name[name] = ct.id

    customers = [
        ("C1", "Customer 1", 26.35, 127.77, 9, 6, "FOB"),
        ("C2", "Customer 2", 35.75, 139.35, 7, 8, "Storefront"),
        ("C3", "Customer 3", 37.09, 127.03, 5, 5, "Storefront"),
        ("C4", "Customer 4", -7.31, 72.41, 3, 4, "Warehouse"),
    ]
    for id_, label, lat, lon, w, h, type_name in customers:
        db.add(models.Customer(id=id_, label=label, lat=lat, lon=lon, w=w, h=h,
                                customer_type_id=type_id_by_name[type_name]))

    # Example policy matching the "40% of missions to Storefront" use case
    db.add(models.MissionAllocationPolicy(customer_type_id=type_id_by_name["Storefront"], target_pct=0.40))

    package_types = [
        ("K1", "Standard", 10, 1.0),
        ("K2", "Fragile", 15, 1.5),
        ("K3", "Hazmat", 25, 2.0),
        ("K4", "Bulk", 40, 4.0),
        ("K5", "Sensitive", 20, 1.5),
    ]
    for id_, name, weight, volume in package_types:
        db.add(models.PackageType(id=id_, name=name, weight=weight, volume=volume))

    method_specs = [
        ("Air", 500, 2000, 150, 1200),
        ("Ground", 55, 5000, 400, 400),
        ("Sea", 23, 50000, 3000, 5000),
    ]
    for method, speed, wcap, vcap, rng in method_specs:
        db.add(models.MethodSpec(method=method, speed_mph=speed, weight_cap=wcap, vol_cap=vcap, range_mi=rng))

    restrictions = [("Air", "K3"), ("Air", "K5"), ("Sea", "K2")]
    for method, k in restrictions:
        db.add(models.MethodRestriction(method=method, package_type_id=k))

    db.flush()

    asset_roster = [
        ("Air-1", "W1", "Air"), ("Air-2", "W1", "Air"), ("Sea-1", "W1", "Sea"),
        ("Air-3", "W2", "Air"), ("Ground-1", "W2", "Ground"), ("Ground-2", "W2", "Ground"),
        ("Ground-3", "W2", "Ground"), ("Sea-2", "W2", "Sea"),
        ("Air-4", "W3", "Air"), ("Ground-4", "W3", "Ground"), ("Ground-5", "W3", "Ground"),
        ("Sea-3", "W4", "Sea"), ("Air-5", "W4", "Air"),
        ("Air-6", "W5", "Air"), ("Ground-6", "W5", "Ground"), ("Ground-7", "W5", "Ground"),
        ("Ground-8", "W5", "Ground"),
    ]
    for id_, home, method in asset_roster:
        db.add(models.Asset(id=id_, home_warehouse_id=home, method=method, team_id=team_id_by_warehouse[home]))

    refuelers = [
        ("Tanker-1", "W1", 1500, 2000),
        ("Tanker-2", "W2", 1500, 2000),
        ("Tanker-3", "W3", 1500, 2000),
    ]
    for id_, home, ext, self_range in refuelers:
        db.add(models.Refueler(id=id_, home_warehouse_id=home, team_id=team_id_by_warehouse[home],
                                extension_mi=ext, self_range_mi=self_range))

    warehouse_inventory = {
        "W1": {"K1": 100, "K2": 30, "K3": 10, "K4": 20, "K5": 5},
        "W2": {"K1": 80, "K2": 20, "K3": 15, "K4": 15, "K5": 10},
        "W3": {"K1": 60, "K2": 15, "K3": 8, "K4": 10, "K5": 6},
        "W4": {"K1": 50, "K2": 10, "K3": 5, "K4": 8, "K5": 4},
        "W5": {"K1": 40, "K2": 10, "K3": 4, "K4": 6, "K5": 3},
    }
    for w_id, items in warehouse_inventory.items():
        for k, qty in items.items():
            db.add(models.WarehouseInventory(warehouse_id=w_id, package_type_id=k, qty=qty))

    customer_bundles = {
        "C1": {"K3": 2, "K5": 5},
        "C2": {"K1": 3, "K2": 4},
        "C3": {"K1": 5, "K4": 2},
        "C4": {"K3": 1, "K5": 1, "K1": 6},
    }
    for c_id, items in customer_bundles.items():
        for k, qty in items.items():
            db.add(models.CustomerBundleItem(customer_id=c_id, package_type_id=k, qty_needed=qty))

    db.add(models.Settings(id=1, cycle_hours=24, handling_time_hours=2, refuel_overhead_hours=3, default_daily_cap=2))

    db.commit()
    print("[seed] done")
