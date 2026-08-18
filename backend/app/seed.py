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

    # (id, label, lat, lon, priority_rank 1=highest, type) — realistic scatter
    # across the theater: some sit near hubs, some are remote or structurally
    # hard to serve, priority is deliberately uncorrelated with distance
    customers = [
        ("C1", "Okinawa FOB", 26.35, 127.77, 1, "FOB"),
        ("C2", "Tokyo Storefront", 35.75, 139.35, 2, "Storefront"),
        ("C3", "Osan Storefront", 37.09, 127.03, 6, "Storefront"),
        ("C4", "Diego Garcia Warehouse", -7.31, 72.41, 20, "Warehouse"),
        ("C5", "Manila DC", 14.60, 120.98, 3, "Distribution Center"),
        ("C6", "Cebu Storefront", 10.30, 123.90, 11, "Storefront"),
        ("C7", "Palau Outpost", 7.34, 134.48, 12, "FOB"),
        ("C8", "Saipan Storefront", 15.19, 145.75, 4, "Storefront"),
        ("C9", "Chuuk Station", 7.45, 151.84, 16, "FOB"),
        ("C10", "Pohnpei Warehouse", 6.96, 158.21, 17, "Warehouse"),
        ("C11", "Kwajalein Site", 8.72, 167.73, 7, "FOB"),
        ("C12", "Majuro Storefront", 7.09, 171.38, 18, "Storefront"),
        ("C13", "Wake Island Outpost", 19.28, 166.65, 8, "FOB"),
        ("C14", "Midway Warehouse", 28.20, -177.35, 13, "Warehouse"),
        ("C15", "Johnston Warehouse", 16.73, -169.53, 21, "Warehouse"),
        ("C16", "Hilo Storefront", 19.72, -155.09, 5, "Storefront"),
        ("C17", "Kauai Storefront", 22.06, -159.50, 14, "Storefront"),
        ("C18", "Pago Pago DC", -14.28, -170.70, 22, "Distribution Center"),
        ("C19", "Fiji DC", -17.75, 177.45, 23, "Distribution Center"),
        ("C20", "Port Moresby Outpost", -9.44, 147.18, 9, "FOB"),
        ("C21", "Townsville DC", -19.26, 146.82, 10, "Distribution Center"),
        ("C22", "Christmas Island Site", -10.45, 105.69, 24, "FOB"),
        ("C23", "Adak Station", 51.88, -176.65, 15, "FOB"),
        ("C24", "Fairbanks DC", 64.84, -147.72, 19, "Distribution Center"),
    ]
    for id_, label, lat, lon, rank, type_name in customers:
        db.add(models.Customer(id=id_, label=label, lat=lat, lon=lon, priority_rank=rank,
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

    db.flush()

    # (id, home, method, vehicle_type) — vehicle types are made-up model
    # names; each location's fleet rolls up to a count per type on page 4
    asset_roster = [
        ("Air-1", "W1", "Air", "Albatross HL"), ("Air-2", "W1", "Air", "Swiftwing 90"),
        ("Sea-1", "W1", "Sea", "Manta-class"),
        ("Air-3", "W2", "Air", "Albatross HL"), ("Ground-1", "W2", "Ground", "Longhaul 8x8"),
        ("Ground-2", "W2", "Ground", "Longhaul 8x8"), ("Ground-3", "W2", "Ground", "Packmule 6"),
        ("Sea-2", "W2", "Sea", "Tiderunner-class"),
        ("Air-4", "W3", "Air", "Swiftwing 90"), ("Ground-4", "W3", "Ground", "Longhaul 8x8"),
        ("Ground-5", "W3", "Ground", "Packmule 6"),
        ("Sea-3", "W4", "Sea", "Manta-class"), ("Air-5", "W4", "Air", "Albatross HL"),
        ("Air-6", "W5", "Air", "Swiftwing 90"), ("Ground-6", "W5", "Ground", "Packmule 6"),
        ("Ground-7", "W5", "Ground", "Longhaul 8x8"), ("Ground-8", "W5", "Ground", "Longhaul 8x8"),
    ]
    for id_, home, method, vtype in asset_roster:
        db.add(models.Asset(id=id_, home_warehouse_id=home, method=method, vehicle_type=vtype,
                             team_id=team_id_by_warehouse[home]))

    # Carrying ability is per-vehicle-type: two vehicles of the same model
    # (e.g. two Packmule 6 trucks) never differ. In this example fleet, both
    # Air models (Albatross HL, Swiftwing 90) are barred from Hazmat and
    # Sensitive, and both Sea models (Manta-class, Tiderunner-class) are
    # barred from Fragile — but that's a property of the model, not the
    # individual vehicle or the transport method.
    vehicle_types_by_method = {}
    for _id, _home, method, vtype in asset_roster:
        vehicle_types_by_method.setdefault(method, set()).add(vtype)
    for vtype in vehicle_types_by_method.get("Air", ()):
        db.add(models.VehicleTypeRestriction(vehicle_type=vtype, package_type_id="K3"))
        db.add(models.VehicleTypeRestriction(vehicle_type=vtype, package_type_id="K5"))
    for vtype in vehicle_types_by_method.get("Sea", ()):
        db.add(models.VehicleTypeRestriction(vehicle_type=vtype, package_type_id="K2"))

    refuelers = [
        ("Tanker-1", "W1", "Pelican KR", 1500, 2000),
        ("Tanker-2", "W2", "Pelican KR", 1500, 2000),
        ("Tanker-3", "W3", "Stork XT", 1500, 2000),
    ]
    for id_, home, vtype, ext, self_range in refuelers:
        db.add(models.Refueler(id=id_, home_warehouse_id=home, vehicle_type=vtype,
                                team_id=team_id_by_warehouse[home],
                                extension_mi=ext, self_range_mi=self_range))

    warehouse_inventory = {
        "W1": {"K1": 300, "K2": 90, "K3": 30, "K4": 60, "K5": 20},
        "W2": {"K1": 240, "K2": 60, "K3": 45, "K4": 45, "K5": 30},
        "W3": {"K1": 180, "K2": 45, "K3": 24, "K4": 30, "K5": 18},
        "W4": {"K1": 150, "K2": 30, "K3": 15, "K4": 24, "K5": 12},
        "W5": {"K1": 120, "K2": 30, "K3": 12, "K4": 18, "K5": 9},
    }
    for w_id, items in warehouse_inventory.items():
        for k, qty in items.items():
            db.add(models.WarehouseInventory(warehouse_id=w_id, package_type_id=k, qty=qty))

    # each line is an alternative — fully delivering any one option satisfies
    customer_bundles = {
        "C1": {"K3": 2, "K5": 5},
        "C2": {"K1": 3, "K2": 4},
        "C3": {"K1": 5, "K4": 2},
        "C4": {"K3": 1, "K5": 1, "K1": 6},
        "C5": {"K1": 8, "K4": 3},
        "C6": {"K1": 4, "K2": 3},
        "C7": {"K3": 1, "K5": 2},
        "C8": {"K1": 3, "K2": 2},
        "C9": {"K1": 5, "K5": 2},
        "C10": {"K4": 2, "K1": 6},
        "C11": {"K3": 2, "K1": 8},
        "C12": {"K1": 3, "K2": 4},
        "C13": {"K5": 3, "K1": 7},
        "C14": {"K1": 4, "K4": 2},
        "C15": {"K3": 1, "K4": 1},
        "C16": {"K1": 2, "K2": 2},
        "C17": {"K2": 3, "K1": 4},
        "C18": {"K1": 5, "K4": 2},
        "C19": {"K4": 3, "K1": 9},
        "C20": {"K3": 2, "K5": 3},
        "C21": {"K1": 6, "K2": 5, "K4": 2},
        "C22": {"K5": 2, "K3": 1},
        "C23": {"K1": 4, "K5": 1},
        "C24": {"K1": 5, "K2": 3},
    }
    for c_id, items in customer_bundles.items():
        for k, qty in items.items():
            db.add(models.CustomerBundleItem(customer_id=c_id, package_type_id=k, qty_needed=qty))

    db.add(models.Settings(id=1, cycle_hours=24, handling_time_hours=2, refuel_overhead_hours=3, default_daily_cap=8))

    db.commit()
    print("[seed] done")
