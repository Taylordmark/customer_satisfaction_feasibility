"""
Builds a snapshot of the current database into plain dicts, computes
distance/reachability/trip-time on the fly (data is editable, so nothing is
precomputed and cached), and answers the four feasibility-assessment pages.

Page 1 — what package options would satisfy the customers (any one
          fulfilled option is enough — lines are alternatives)
Page 2 — what transports can move those packages (their carrying ability)
Page 3 — what warehouses have both the packages and a transport with
          sufficient range (direct or refueled) to deliver them
Page 4 — what support (refuelers) each delivery needs, with the controlling
          team shown per vehicle, plus the fleet stationed at each location
"""

import logging

from sqlalchemy.orm import Session
from . import models
from .geo import haversine, initial_bearing, destination_point

logger = logging.getLogger(__name__)


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

    # per-asset carrying restrictions: disallowed[asset_id] = {package_type_id, ...}
    disallowed = {a: set() for a in assets}
    for r in db.query(models.AssetRestriction).all():
        disallowed.setdefault(r.asset_id, set()).add(r.package_type_id)

    inventory = {}
    for inv in db.query(models.WarehouseInventory).all():
        inventory[(inv.warehouse_id, inv.package_type_id)] = inv.qty

    bundles = {}
    for item in db.query(models.CustomerBundleItem).all():
        bundles.setdefault(item.customer_id, {})[item.package_type_id] = item.qty_needed

    allocation_policies = {p.customer_type_id: p for p in db.query(models.MissionAllocationPolicy).all()}
    planned_missions = db.query(models.PlannedMission).all()

    return {
        "warehouses": warehouses, "teams": teams, "customer_types": customer_types,
        "customers": customers, "package_types": package_types, "method_specs": method_specs,
        "assets": assets, "refuelers": refuelers, "settings": settings,
        "disallowed": disallowed, "inventory": inventory, "bundles": bundles,
        "allocation_policies": allocation_policies, "planned_missions": planned_missions,
    }


def compute_reachability(ctx: dict) -> dict:
    """Adds dist / reach / reach_ext / trip_time to the context, keyed by
    asset id and customer id, mirroring the standalone model's logic.

    Also adds data_warnings: human-readable strings naming any asset whose
    method spec is too broken to compute reachability for (speed_mph <= 0
    would divide by zero for trip time; range_mi <= 0 makes every distance
    unreachable anyway) — such an asset is treated as reaching nothing
    rather than raising, and the problem is surfaced instead of silently
    swallowed."""
    warehouses, customers, assets, refuelers = ctx["warehouses"], ctx["customers"], ctx["assets"], ctx["refuelers"]
    method_specs = ctx["method_specs"]
    settings = ctx["settings"]

    dist = {r: {c: haversine(warehouses[r].lat, warehouses[r].lon, customers[c].lat, customers[c].lon)
                for c in customers} for r in warehouses}

    reach, reach_ext, trip_time = {}, {}, {}
    data_warnings = []
    for a_id, asset in assets.items():
        spec = method_specs.get(asset.method)
        reach[a_id], reach_ext[a_id], trip_time[a_id] = {}, {}, {}
        if spec is None:
            continue
        if spec.speed_mph <= 0 or spec.range_mi <= 0:
            msg = (f"{a_id} uses method '{asset.method}' with an invalid spec "
                   f"(speed_mph={spec.speed_mph:g}, range_mi={spec.range_mi:g}) — "
                   "treated as unreachable everywhere until the data is fixed.")
            logger.warning("[feasibility] %s", msg)
            data_warnings.append(msg)
            continue  # reach[a_id]/reach_ext[a_id]/trip_time[a_id] stay empty
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
    ctx["data_warnings"] = data_warnings
    return ctx


def get_context(db: Session) -> dict:
    return compute_reachability(build_context(db))


# ---------------------------------------------------------------------------
# Page 1 — what package options would satisfy the customers
#          (any one fulfilled option is enough — lines are alternatives)
# ---------------------------------------------------------------------------
def page1_bundles(ctx: dict) -> list:
    out = []
    for c_id, cust in sorted(ctx["customers"].items(), key=lambda kv: kv[1].priority_rank):
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
            "customer_id": c_id, "label": cust.label, "rank": cust.priority_rank,
            "customer_type": type_name, "items": items,
        })
    return out


# ---------------------------------------------------------------------------
# Page 2 — what transports can move the packages (carrying ability)
# ---------------------------------------------------------------------------
def page2_transports(ctx: dict) -> list:
    """Carrying ability is per-vehicle, not per method — Sea-1 may take a
    package Sea-2 can't."""
    out = []
    for k_id, pt in ctx["package_types"].items():
        eligible_assets, barred_assets = [], []
        for a_id in ctx["assets"]:
            if k_id in ctx["disallowed"].get(a_id, set()):
                barred_assets.append(a_id)
            else:
                eligible_assets.append(a_id)
        out.append({
            "package_type_id": k_id, "name": pt.name,
            "eligible_assets": sorted(eligible_assets),
            "barred_assets": sorted(barred_assets),
        })
    return out


# ---------------------------------------------------------------------------
# Page 3 — warehouses with both stock and a transport that can reach
# ---------------------------------------------------------------------------
def page3_locations(ctx: dict) -> list:
    out = []
    for c_id, cust in sorted(ctx["customers"].items(), key=lambda kv: kv[1].priority_rank):
        pkg_results = []
        for k_id, qty_needed in ctx["bundles"].get(c_id, {}).items():
            warehouse_results = []
            for w_id, wh in ctx["warehouses"].items():
                stock = ctx["inventory"].get((w_id, k_id), 0)
                assets_here = [
                    a_id for a_id, a in ctx["assets"].items()
                    if a.home_warehouse_id == w_id and k_id not in ctx["disallowed"].get(a_id, set())
                ]
                asset_status = []
                for a_id in assets_here:
                    a = ctx["assets"][a_id]
                    direct = ctx["reach"][a_id].get(c_id, False)
                    # out-of-service refuelers can't actually support a run —
                    # a vehicle "reachable" only via one isn't really capable
                    via = ([] if direct else
                           [f for f, ok in ctx["reach_ext"][a_id].get(c_id, {}).items()
                            if ok and ctx["refuelers"][f].available])
                    if direct or via:
                        asset_status.append({"asset_id": a_id, "method": a.method,
                                              "direct": direct, "via_refuelers": via,
                                              "available": a.available})
                # verdicts (feasible/partial) match page 5: only vehicles
                # actually in service today count, though every capable
                # asset is still listed (grayed out in the UI if unavailable)
                available_capable = [s for s in asset_status if s["available"]]
                feasible = stock >= qty_needed and len(available_capable) > 0
                partial = 0 < stock < qty_needed and len(available_capable) > 0
                if stock > 0 or asset_status:
                    warehouse_results.append({
                        "warehouse_id": w_id, "label": wh.label, "stock": stock,
                        "capable_assets": asset_status, "feasible": feasible,
                        "partial": partial,
                    })
            pkg_results.append({
                "package_type_id": k_id, "qty_needed": qty_needed,
                "warehouses": warehouse_results,
                "any_feasible": any(w["feasible"] for w in warehouse_results),
            })
        out.append({
            "customer_id": c_id, "label": cust.label,
            "packages": pkg_results,
            # bundle lines are alternatives: one sourceable option is enough
            "fully_feasible": any(p["any_feasible"] for p in pkg_results),
        })
    return out


# ---------------------------------------------------------------------------
# Page 4 — what support does each delivery need (refuelers), and who controls
#          the vehicles involved (tasking authority follows from the
#          location/vehicle combination, so it's shown inline per vehicle)
# ---------------------------------------------------------------------------
def page4_support(ctx: dict) -> dict:
    def team_name(t_id):
        return ctx["teams"][t_id].name if t_id in ctx["teams"] else "Unassigned"

    per_customer = []
    for c_id, cust in sorted(ctx["customers"].items(), key=lambda kv: kv[1].priority_rank):
        bundle = ctx["bundles"].get(c_id, {})
        direct_assets, supported_assets = [], []
        for a_id, a in ctx["assets"].items():
            carriable = [k for k in bundle if k not in ctx["disallowed"].get(a_id, set())]
            if not carriable:
                continue
            row = {
                "asset_id": a_id, "method": a.method, "vehicle_type": a.vehicle_type,
                "warehouse_id": a.home_warehouse_id,
                "team": team_name(a.team_id), "carries": sorted(carriable),
                "available": a.available,
            }
            if ctx["reach"][a_id].get(c_id, False):
                direct_assets.append(row)
            else:
                tankers = []
                for f_id, ok in ctx["reach_ext"][a_id].get(c_id, {}).items():
                    if ok:
                        f = ctx["refuelers"][f_id]
                        tankers.append({"refueler_id": f_id, "warehouse_id": f.home_warehouse_id,
                                        "team": team_name(f.team_id), "available": f.available})
                if tankers:
                    supported_assets.append({**row, "refuelers": tankers})

        # out-of-service assets/refuelers stay listed (grayed out in the UI)
        # but don't count toward the verdict, so pages 3/4 agree with page 5
        available_direct = [r for r in direct_assets if r["available"]]
        available_supported = [
            r for r in supported_assets
            if r["available"] and any(t["available"] for t in r["refuelers"])
        ]
        per_customer.append({
            "customer_id": c_id, "label": cust.label,
            # support is required when no available capable asset reaches unaided
            "needs_support": not available_direct and bool(available_supported),
            "unreachable": not available_direct and not available_supported,
            "direct_assets": direct_assets,
            "supported_assets": supported_assets,
        })

    # fleet-by-location rollup: what's stationed where, who controls it, and
    # a count per vehicle type (model) at each location
    by_location = []
    for w_id, wh in ctx["warehouses"].items():
        assets_here = [{"asset_id": a_id, "method": a.method, "vehicle_type": a.vehicle_type,
                        "available": a.available, "team": team_name(a.team_id)}
                       for a_id, a in ctx["assets"].items() if a.home_warehouse_id == w_id]
        refuelers_here = [{"refueler_id": f_id, "vehicle_type": f.vehicle_type,
                           "available": f.available, "team": team_name(f.team_id)}
                          for f_id, f in ctx["refuelers"].items() if f.home_warehouse_id == w_id]
        type_counts = {}
        for a in assets_here:
            type_counts[a["vehicle_type"]] = type_counts.get(a["vehicle_type"], 0) + 1
        for f in refuelers_here:
            type_counts[f["vehicle_type"]] = type_counts.get(f["vehicle_type"], 0) + 1
        by_location.append({
            "warehouse_id": w_id, "label": wh.label,
            "assets": assets_here, "refuelers": refuelers_here,
            "type_counts": type_counts,
        })

    return {"per_customer": per_customer, "by_location": by_location}
