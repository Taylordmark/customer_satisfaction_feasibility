"""
Builds a snapshot of the current database into plain dicts, computes
distance/reachability/trip-time on the fly (data is editable, so nothing is
precomputed and cached), and answers the four feasibility-assessment pages.

Page 1 — what packages, and how many, would satisfy the customers
Page 2 — what transports can move those packages (their carrying ability)
Page 3 — what warehouses have both the packages and a transport with
          sufficient range (direct or refueled) to deliver them
Page 4 — which transport control teams own/can task the relevant assets
"""

from sqlalchemy.orm import Session
from . import models
from .geo import haversine, initial_bearing, destination_point


def build_context(db: Session) -> dict:
    warehouses = {w.id: w for w in db.query(models.Warehouse).all()}
    teams = {t.id: t for t in db.query(models.TransportControlTeam).all()}
    customer_types = {ct.id: ct for ct in db.query(models.CustomerType).all()}
    customers = {c.id: c for c in db.query(models.Customer).all()}
    package_types = {p.id: p for p in db.query(models.PackageType).all()}
    method_specs = {m.method: m for m in db.query(models.MethodSpec).all()}
    assets = {a.id: a for a in db.query(models.Asset).all()}
    refuelers = {f.id: f for f in db.query(models.Refueler).all()}
    settings = db.query(models.Settings).first()

    disallowed = {m: set() for m in method_specs}
    for r in db.query(models.MethodRestriction).all():
        disallowed.setdefault(r.method, set()).add(r.package_type_id)

    inventory = {}
    for inv in db.query(models.WarehouseInventory).all():
        inventory[(inv.warehouse_id, inv.package_type_id)] = inv.qty

    bundles = {}
    for item in db.query(models.CustomerBundleItem).all():
        bundles.setdefault(item.customer_id, {})[item.package_type_id] = item.qty_needed

    allocation_policies = {p.customer_type_id: p for p in db.query(models.MissionAllocationPolicy).all()}

    return {
        "warehouses": warehouses, "teams": teams, "customer_types": customer_types,
        "customers": customers, "package_types": package_types, "method_specs": method_specs,
        "assets": assets, "refuelers": refuelers, "settings": settings,
        "disallowed": disallowed, "inventory": inventory, "bundles": bundles,
        "allocation_policies": allocation_policies,
    }


def compute_reachability(ctx: dict) -> dict:
    """Adds dist / reach / reach_ext / trip_time to the context, keyed by
    asset id and customer id, mirroring the standalone model's logic."""
    warehouses, customers, assets, refuelers = ctx["warehouses"], ctx["customers"], ctx["assets"], ctx["refuelers"]
    method_specs = ctx["method_specs"]
    settings = ctx["settings"]

    dist = {r: {c: haversine(warehouses[r].lat, warehouses[r].lon, customers[c].lat, customers[c].lon)
                for c in customers} for r in warehouses}

    reach, reach_ext, trip_time = {}, {}, {}
    for a_id, asset in assets.items():
        spec = method_specs.get(asset.method)
        reach[a_id], reach_ext[a_id], trip_time[a_id] = {}, {}, {}
        if spec is None:
            continue
        home = asset.home_warehouse_id
        for c_id in customers:
            d = dist[home][c_id]
            direct_ok = d <= spec.range_mi
            reach[a_id][c_id] = direct_ok
            reach_ext[a_id][c_id] = {}

            if direct_ok:
                trip_time[a_id][c_id] = 2 * d / spec.speed_mph + settings.handling_time_hours
                continue

            bearing = initial_bearing(warehouses[home].lat, warehouses[home].lon, customers[c_id].lat, customers[c_id].lon)
            rlat, rlon = destination_point(warehouses[home].lat, warehouses[home].lon, bearing, spec.range_mi)
            for f_id, f in refuelers.items():
                within_ext = d <= spec.range_mi + f.extension_mi
                if not within_ext:
                    reach_ext[a_id][c_id][f_id] = False
                    continue
                tanker_dist = haversine(warehouses[f.home_warehouse_id].lat, warehouses[f.home_warehouse_id].lon, rlat, rlon)
                reach_ext[a_id][c_id][f_id] = tanker_dist <= f.self_range_mi

            trip_time[a_id][c_id] = 2 * d / spec.speed_mph + settings.handling_time_hours + settings.refuel_overhead_hours

    ctx["dist"] = dist
    ctx["reach"] = reach
    ctx["reach_ext"] = reach_ext
    ctx["trip_time"] = trip_time
    return ctx


def get_context(db: Session) -> dict:
    return compute_reachability(build_context(db))


# ---------------------------------------------------------------------------
# Page 1 — what packages, and how many, would satisfy the customers
# ---------------------------------------------------------------------------
def page1_bundles(ctx: dict) -> list:
    out = []
    for c_id, cust in ctx["customers"].items():
        items = []
        for k_id, qty in ctx["bundles"].get(c_id, {}).items():
            pt = ctx["package_types"].get(k_id)
            items.append({
                "package_type_id": k_id,
                "name": pt.name if pt else k_id,
                "qty_needed": qty,
            })
        type_name = ctx["customer_types"][cust.customer_type_id].name if cust.customer_type_id in ctx["customer_types"] else None
        out.append({
            "customer_id": c_id, "label": cust.label, "score": cust.score,
            "customer_type": type_name, "items": items,
        })
    return out


# ---------------------------------------------------------------------------
# Page 2 — what transports can move the packages (carrying ability)
# ---------------------------------------------------------------------------
def page2_transports(ctx: dict) -> list:
    out = []
    for k_id, pt in ctx["package_types"].items():
        eligible_methods = [m for m in ctx["method_specs"] if k_id not in ctx["disallowed"].get(m, set())]
        eligible_assets = [a_id for a_id, a in ctx["assets"].items() if a.method in eligible_methods]
        barred_methods = [m for m in ctx["method_specs"] if m not in eligible_methods]
        out.append({
            "package_type_id": k_id, "name": pt.name,
            "eligible_methods": eligible_methods,
            "barred_methods": barred_methods,
            "eligible_assets": eligible_assets,
        })
    return out


# ---------------------------------------------------------------------------
# Page 3 — warehouses with both stock and a transport that can reach
# ---------------------------------------------------------------------------
def page3_locations(ctx: dict) -> list:
    out = []
    for c_id, cust in ctx["customers"].items():
        pkg_results = []
        for k_id, qty_needed in ctx["bundles"].get(c_id, {}).items():
            eligible_methods = {m for m in ctx["method_specs"] if k_id not in ctx["disallowed"].get(m, set())}
            warehouse_results = []
            for w_id, wh in ctx["warehouses"].items():
                stock = ctx["inventory"].get((w_id, k_id), 0)
                assets_here = [
                    a_id for a_id, a in ctx["assets"].items()
                    if a.home_warehouse_id == w_id and a.method in eligible_methods
                ]
                asset_status = []
                for a_id in assets_here:
                    direct = ctx["reach"][a_id].get(c_id, False)
                    via = [f for f, ok in ctx["reach_ext"][a_id].get(c_id, {}).items() if ok] if not direct else []
                    if direct or via:
                        asset_status.append({"asset_id": a_id, "method": ctx["assets"][a_id].method,
                                              "direct": direct, "via_refuelers": via})
                feasible = stock > 0 and len(asset_status) > 0
                if stock > 0 or asset_status:
                    warehouse_results.append({
                        "warehouse_id": w_id, "label": wh.label, "stock": stock,
                        "capable_assets": asset_status, "feasible": feasible,
                    })
            pkg_results.append({
                "package_type_id": k_id, "qty_needed": qty_needed,
                "warehouses": warehouse_results,
                "any_feasible": any(w["feasible"] for w in warehouse_results),
            })
        out.append({
            "customer_id": c_id, "label": cust.label,
            "packages": pkg_results,
            "fully_feasible": all(p["any_feasible"] for p in pkg_results) if pkg_results else False,
        })
    return out


# ---------------------------------------------------------------------------
# Page 4 — which transport control teams own/can task the relevant assets
# ---------------------------------------------------------------------------
def page4_teams(ctx: dict) -> dict:
    org_chart = []
    for t_id, t in ctx["teams"].items():
        org_chart.append({
            "team_id": t_id, "name": t.name, "warehouse_id": t.warehouse_id,
            "assets": [a_id for a_id, a in ctx["assets"].items() if a.team_id == t_id],
            "refuelers": [f_id for f_id, f in ctx["refuelers"].items() if f.team_id == t_id],
        })
    unowned_assets = [a_id for a_id, a in ctx["assets"].items() if a.team_id is None]

    per_customer = []
    for c_id, cust in ctx["customers"].items():
        needed_teams = {}
        for k_id in ctx["bundles"].get(c_id, {}):
            eligible_methods = {m for m in ctx["method_specs"] if k_id not in ctx["disallowed"].get(m, set())}
            for a_id, a in ctx["assets"].items():
                if a.method not in eligible_methods:
                    continue
                direct = ctx["reach"][a_id].get(c_id, False)
                via = any(ctx["reach_ext"][a_id].get(c_id, {}).values())
                if direct or via:
                    t_id = a.team_id
                    t_name = ctx["teams"][t_id].name if t_id in ctx["teams"] else "Unassigned"
                    needed_teams.setdefault((t_id, t_name), set()).add(a_id)
        per_customer.append({
            "customer_id": c_id, "label": cust.label,
            "teams_to_coordinate": [
                {"team_id": t_id, "team_name": t_name, "assets": sorted(a_ids)}
                for (t_id, t_name), a_ids in needed_teams.items()
            ],
        })

    return {"org_chart": org_chart, "unowned_assets": unowned_assets, "per_customer": per_customer}
