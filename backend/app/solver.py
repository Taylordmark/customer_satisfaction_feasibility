"""
Page 5 — given a cap on how many delivery missions can be scheduled in a
day, how many of the customers' needed deliveries can actually be scheduled?

Reuses the same MILP structure as the standalone model (dispatch, refuel
pairing, bundle satisfaction, capacity, inventory, time budget) plus:
  - a global cap on total missions scheduled that day
  - minimum-share-by-customer-type quotas (mission allocation policy),
    e.g. "at least 40% of missions go to Storefront-type customers"
"""

import pulp
from .feasibility import get_context


def solve_daily_cap(db, daily_cap: int) -> dict:
    print(f"[solver] building model for daily_cap={daily_cap}")
    ctx = get_context(db)
    customers, assets, refuelers = ctx["customers"], ctx["assets"], ctx["refuelers"]
    package_types, bundles = ctx["package_types"], ctx["bundles"]
    disallowed, inventory = ctx["disallowed"], ctx["inventory"]
    reach, reach_ext, trip_time = ctx["reach"], ctx["reach_ext"], ctx["trip_time"]
    settings = ctx["settings"]
    allocation_policies = ctx["allocation_policies"]
    customer_types = ctx["customer_types"]

    # candidate (asset, customer) pairs: only where a bundle exists and some
    # reach path (direct or refueled) is possible
    z_candidates, p_candidates = [], []
    for a_id, a in assets.items():
        for c_id in customers:
            if c_id not in bundles or not bundles[c_id]:
                continue
            direct = reach[a_id].get(c_id, False)
            tanker_opts = [f for f, ok in reach_ext[a_id].get(c_id, {}).items() if ok]
            if direct or tanker_opts:
                z_candidates.append((a_id, c_id))
            for f_id in tanker_opts:
                p_candidates.append((a_id, c_id, f_id))

    print(f"[solver] {len(z_candidates)} dispatch candidates, {len(p_candidates)} refuel-pairing candidates")
    print(f"[solver] {len(allocation_policies)} mission-allocation policies active")

    model = pulp.LpProblem("page5_daily_cap", pulp.LpMaximize)
    z = {(a, c): pulp.LpVariable(f"z_{a}_{c}", cat="Binary") for (a, c) in z_candidates}
    p = {(a, c, f): pulp.LpVariable(f"p_{a}_{c}_{f}", cat="Binary") for (a, c, f) in p_candidates}
    y = {c: pulp.LpVariable(f"y_{c}", cat="Binary") for c in customers if c in bundles and bundles[c]}

    x = {}
    for (a, c) in z_candidates:
        method = assets[a].method
        barred = disallowed.get(method, set())
        for k, qty_needed in bundles[c].items():
            if k in barred:
                continue
            x[(a, c, k)] = pulp.LpVariable(f"x_{a}_{c}_{k}", lowBound=0, upBound=qty_needed, cat="Integer")

    model += pulp.lpSum(customers[c].score * y[c] for c in y), "objective"

    # time budget per asset
    for a in assets:
        terms = [trip_time[a][c] * z[(a, c)] for c in customers if (a, c) in z]
        if terms:
            model += pulp.lpSum(terms) <= settings.cycle_hours

    # weight / volume tied to dispatch
    for (a, c) in z_candidates:
        w_terms = [package_types[k].weight * x[(a, c, k)] for k in bundles[c] if (a, c, k) in x]
        v_terms = [package_types[k].volume * x[(a, c, k)] for k in bundles[c] if (a, c, k) in x]
        spec = ctx["method_specs"][assets[a].method]
        if w_terms:
            model += pulp.lpSum(w_terms) <= spec.weight_cap * z[(a, c)]
        if v_terms:
            model += pulp.lpSum(v_terms) <= spec.vol_cap * z[(a, c)]

    # warehouse inventory
    for w_id in ctx["warehouses"]:
        assets_at_w = [a for a, av in assets.items() if av.home_warehouse_id == w_id]
        for k in package_types:
            terms = [x[(a, c, k)] for a in assets_at_w for c in customers if (a, c, k) in x]
            if terms:
                model += pulp.lpSum(terms) <= inventory.get((w_id, k), 0)

    # bundle satisfaction
    for c in y:
        for k, qty_needed in bundles[c].items():
            terms = [x[(a, c, k)] for a in assets if (a, c, k) in x]
            model += pulp.lpSum(terms) >= qty_needed * y[c]

    # reachability
    for (a, c) in z_candidates:
        direct_ok = 1 if reach[a].get(c, False) else 0
        refuel_terms = [p[(a, c, f)] for f in refuelers if (a, c, f) in p]
        model += z[(a, c)] <= direct_ok + pulp.lpSum(refuel_terms)

    # pairing requires dispatch
    for (a, c, f) in p_candidates:
        model += p[(a, c, f)] <= z[(a, c)]

    # one rendezvous per refueler
    for f in refuelers:
        trips = [p[(a, c, f)] for (a, c, ff) in p_candidates if ff == f]
        if trips:
            model += pulp.lpSum(trips) <= 1

    # global daily mission cap
    if z:
        model += pulp.lpSum(z.values()) <= daily_cap, "daily_delivery_cap"

    # mission-allocation-by-customer-type quotas:
    # missions to type T  >=  target_pct * missions scheduled overall
    all_z_terms = list(z.values())
    for ct_id, policy in allocation_policies.items():
        type_name = customer_types[ct_id].name if ct_id in customer_types else f"type {ct_id}"
        customers_of_type = [c_id for c_id, cust in customers.items() if cust.customer_type_id == ct_id]
        type_terms = [z[(a, c)] for (a, c) in z_candidates if c in customers_of_type]
        if not type_terms:
            print(f"[solver] policy for '{type_name}' has no matching schedulable customers — skipping")
            continue
        model += (
            pulp.lpSum(type_terms) >= policy.target_pct * pulp.lpSum(all_z_terms),
            f"quota_{ct_id}",
        )
        print(f"[solver] quota: >= {policy.target_pct*100:.0f}% of missions go to '{type_name}'")

    print(f"[solver] solving with CBC...")
    model.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[model.status]
    print(f"[solver] status={status} objective={pulp.value(model.objective)}")

    dispatches = []
    for (a, c) in z_candidates:
        if pulp.value(z[(a, c)]) > 0.5:
            shipped = {k: int(pulp.value(x[(a, c, k)])) for k in bundles[c]
                       if (a, c, k) in x and pulp.value(x[(a, c, k)]) > 0}
            paired = [f for f in refuelers if (a, c, f) in p and pulp.value(p[(a, c, f)]) > 0.5]
            dispatches.append({
                "asset_id": a, "home_warehouse_id": assets[a].home_warehouse_id, "method": assets[a].method,
                "customer_id": c, "refueler_id": paired[0] if paired else None, "cargo": shipped,
            })

    # per-type mission counts, for verifying the quota visually on the frontend
    type_counts = {}
    for d in dispatches:
        c_id = d["customer_id"]
        ct_id = customers[c_id].customer_type_id
        type_name = customer_types[ct_id].name if ct_id in customer_types else "Unassigned"
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    customer_results = []
    for c_id, cust in customers.items():
        if c_id not in y:
            continue
        satisfied = pulp.value(y[c_id]) > 0.5
        shortfall = {}
        if not satisfied:
            for k, qty_needed in bundles[c_id].items():
                shipped = sum(int(pulp.value(x[(a, c_id, k)])) for a in assets if (a, c_id, k) in x)
                if shipped < qty_needed:
                    shortfall[k] = {"needed": qty_needed, "shipped": shipped}
        type_name = customer_types[cust.customer_type_id].name if cust.customer_type_id in customer_types else None
        customer_results.append({
            "customer_id": c_id, "label": cust.label, "score": cust.score,
            "customer_type": type_name, "satisfied": satisfied, "shortfall": shortfall,
        })

    total_possible = sum(customers[c].score for c in y)
    achieved = sum(customers[c].score for c in y if pulp.value(y[c]) > 0.5)

    return {
        "status": status,
        "daily_cap": daily_cap,
        "deliveries_scheduled": len(dispatches),
        "score_achieved": achieved,
        "score_possible": total_possible,
        "mission_counts_by_type": type_counts,
        "customers": customer_results,
        "dispatches": dispatches,
    }
