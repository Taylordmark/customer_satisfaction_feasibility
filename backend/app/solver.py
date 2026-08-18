"""
Page 5 — given a cap on how many delivery missions can be scheduled in a
day, how many of the customers' needed deliveries can actually be scheduled?

Every run solves the same MILP (dispatch, refuel pairing, bundle-option
satisfaction, capacity, inventory, time budget, daily cap, per-type mission
quotas) once per objective mode, so the user can compare and choose:

  - max_count:        maximize the number of customers satisfied (all equal)
  - rank_weighted:    maximize rank-weighted satisfaction — rank r of N gets
                      weight N+1-r (floored at 1), so priority matters but
                      several mid-ranked customers can outweigh one top-ranked
  - strict_priority:  true lexicographic solve — customers are grouped by
                      priority_rank and solved best-rank-first, freezing each
                      group's achieved satisfied-count before moving to the
                      next, so a higher-ranked customer is never sacrificed
                      for any number of lower-ranked ones, exactly, at any
                      customer count (no weight-doubling approximation)

Human decisions layer on top of the master data and constrain every mode:
  - customers can be excluded from today's plan (Customer.included)
  - vehicles / refuelers can be marked out of service (available flags)
  - PlannedMission rows pin missions at any level of detail; pins are hard
    constraints that count against the cap and quotas. Conflicting pins make
    the run refuse with an explanation instead of being silently dropped.
"""

import logging
import os
import subprocess
import threading
from collections import defaultdict

import pulp
from .feasibility import get_context

logger = logging.getLogger(__name__)

# Concurrent /page5 requests are serialized rather than left to stack up
# multiple simultaneous CBC/HiGHS subprocesses against the same machine.
_solve_lock = threading.Lock()

_solver_backend = None  # "cbc" | "highs" — probed once per process


def _detect_backend():
    # PuLP ships a prebuilt CBC binary that exists on every platform but
    # can't always execute (e.g. it's x86-only, so arm64 macs without
    # Rosetta raise "Bad CPU type"). available() only checks the file
    # exists, so probe the binary once and fall back to HiGHS (pip-installed,
    # all architectures).
    global _solver_backend
    if _solver_backend is None:
        cbc = pulp.PULP_CBC_CMD(msg=False)
        try:
            subprocess.run([cbc.path, "exit"], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=10)
            _solver_backend = "cbc"
        except OSError:
            logger.warning("[solver] bundled CBC binary unusable on this host, using HiGHS")
            _solver_backend = "highs"
    return _solver_backend


def _time_limit_s() -> float:
    """Per-solve wall-clock budget, read fresh from the environment each
    call (not a Settings column — there's no migration tooling, so adding
    one would risk breaking existing DB volumes on upgrade)."""
    raw = os.environ.get("SOLVER_TIME_LIMIT_S", "60")
    try:
        val = float(raw)
        if val <= 0:
            raise ValueError
        return val
    except ValueError:
        logger.warning("[solver] invalid SOLVER_TIME_LIMIT_S=%r, using 60s", raw)
        return 60.0


def _get_solver(time_limit: float):
    """A fresh solver instance per solve — PULP_CBC_CMD/HiGHS take timeLimit
    at construction time, and re-solving the same wrapper instance isn't a
    supported pattern for the CMD backend."""
    if _detect_backend() == "cbc":
        return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
    return pulp.HiGHS(msg=False, timeLimit=time_limit)


def _is_time_limited(model) -> bool:
    """True iff the solve stopped on the time limit with a feasible-but-not-
    proven-optimal incumbent, for either backend in use.

    Verified empirically: both PULP_CBC_CMD (coin_api.get_status — a CBC sol
    file beginning "Stopped on time - objective value X" maps to
    (LpStatusOptimal, LpSolutionIntegerFeasible)) and pulp.HiGHS
    (highs_api.findSolutionValues — HighsModelStatus.kTimeLimit maps to the
    same pair) report LpStatus "Optimal" in both the true-optimal and
    time-limited-with-incumbent cases; only `sol_status` distinguishes them
    (LpSolutionOptimal vs LpSolutionIntegerFeasible). A genuinely Infeasible
    model gets LpSolutionInfeasible, never IntegerFeasible, so this flag is
    always independent of (and never conflated with) an Infeasible status.
    """
    return getattr(model, "sol_status", None) == pulp.LpSolutionIntegerFeasible


OBJECTIVE_MODES = [
    ("max_count", "Most customers satisfied",
     "Every customer counts equally — maximizes the number of completed orders."),
    ("rank_weighted", "Rank-weighted",
     "Rank r of N gets weight N+1−r (floored at 1). Priority matters, but a few "
     "mid-ranked customers can outweigh one top-ranked customer."),
    ("strict_priority", "Highest ranks first",
     "True lexicographic priority — solved rank group by rank group, best "
     "first. A higher-ranked customer is never sacrificed for any number of "
     "lower-ranked ones."),
]


def _weights_for_mode(mode, customers, eligible):
    """Objective weight per satisfiable customer, for the two modes that use
    a single weighted-sum objective (strict_priority is solved separately,
    lexicographically — see _solve_lexicographic)."""
    if mode == "max_count":
        return {c: 1 for c in eligible}
    if mode == "rank_weighted":
        n = len(customers)
        # floor at 1: a priority_rank beyond len(customers) (stale/bad data)
        # must never go negative and make the objective actively avoid
        # satisfying that customer.
        return {c: max(1, n + 1 - customers[c].priority_rank) for c in eligible}
    raise ValueError(f"_weights_for_mode: unsupported mode {mode!r}")


def _build_candidates(ctx, eligible):
    """(asset, customer) dispatch candidates and (asset, customer, refueler)
    pairing candidates, honoring availability flags and today's customer set."""
    z_candidates, p_candidates = [], []
    disallowed, bundles = ctx["disallowed"], ctx["bundles"]
    for a_id, a in ctx["assets"].items():
        if not a.available:
            continue
        barred = disallowed.get(a_id, set())
        for c_id in eligible:
            # an asset barred from every one of the customer's bundle options
            # can never carry anything to them — it would only ever be
            # "dispatched" empty, which is exactly the phantom-mission bug.
            bundle = bundles.get(c_id)
            if bundle and barred.issuperset(bundle.keys()):
                continue
            direct = ctx["reach"][a_id].get(c_id, False)
            tanker_opts = [f for f, ok in ctx["reach_ext"][a_id].get(c_id, {}).items()
                           if ok and ctx["refuelers"][f].available]
            if direct or tanker_opts:
                z_candidates.append((a_id, c_id))
            for f_id in tanker_opts:
                p_candidates.append((a_id, c_id, f_id))
    return z_candidates, p_candidates


def _validate_pins(ctx, eligible, z_set, p_set, daily_cap):
    """Turn PlannedMission rows into hard-constraint specs, or explain why
    they can't be honored. Returns (pins, conflicts)."""
    customers, assets, refuelers = ctx["customers"], ctx["assets"], ctx["refuelers"]
    bundles, disallowed = ctx["bundles"], ctx["disallowed"]
    trip_time, cycle = ctx["trip_time"], ctx["settings"].cycle_hours

    # a dispatch is only actually flyable if the round trip fits in the cycle
    def fits_cycle(a, c):
        return trip_time.get(a, {}).get(c, float("inf")) <= cycle

    reachable_in_cycle = {c for (a, c) in z_set if fits_cycle(a, c)}

    pins = {"y": set(), "z": set(), "p": set(), "s": set(), "source": {}, "rows": []}
    conflicts = []

    # --- cross-row consistency per customer: contradictory pins are a
    # conflict, not a silent last-write-wins (M5 + the option-pin analogue).
    by_customer = defaultdict(list)
    for row in ctx["planned_missions"]:
        by_customer[row.customer_id].append(row)

    conflicted_customers = set()
    for c, rows in by_customer.items():
        label = customers[c].label if c in customers else c
        distinct_sources = {r.source_warehouse_id for r in rows if r.source_warehouse_id}
        distinct_packages = {r.package_type_id for r in rows if r.package_type_id}
        if len(distinct_sources) > 1:
            conflicts.append(
                f"{label}: {len(rows)} pins name different source warehouses "
                f"({', '.join(sorted(distinct_sources))}) for the same customer — "
                "pick one source or remove the extra pin."
            )
            conflicted_customers.add(c)
        if len(distinct_packages) > 1:
            conflicts.append(
                f"{label}: pins name different bundle options "
                f"({', '.join(sorted(distinct_packages))}) for the same customer — "
                "forcing more than one option to full delivery is almost certainly "
                "not intended; pick one or remove the extra pin."
            )
            conflicted_customers.add(c)

    for row in ctx["planned_missions"]:
        c = row.customer_id
        if c in conflicted_customers:
            continue  # already reported above as a cross-row conflict
        label = customers[c].label if c in customers else c
        desc = [f"{label}"]
        if row.asset_id:
            desc.append(f"via {row.asset_id}")
        if row.refueler_id:
            desc.append(f"with {row.refueler_id}")
        if row.package_type_id:
            desc.append(f"delivering {row.package_type_id}")
        if row.source_warehouse_id:
            desc.append(f"from {row.source_warehouse_id}")
        pin_desc = " ".join(desc)

        if c not in customers:
            conflicts.append(f"Pin '{pin_desc}': unknown customer {c}.")
            continue
        if not customers[c].included:
            conflicts.append(f"Pin '{pin_desc}': customer is excluded from today's plan.")
            continue
        if not bundles.get(c):
            conflicts.append(f"Pin '{pin_desc}': customer has no bundle defined.")
            continue
        if c not in reachable_in_cycle:
            conflicts.append(f"Pin '{pin_desc}': no available vehicle can reach {label} and "
                             f"return within the {cycle:g}-hour cycle — the customer is "
                             "structurally unservable today.")
            continue

        ok = True
        if row.asset_id:
            a = row.asset_id
            if a not in assets:
                conflicts.append(f"Pin '{pin_desc}': unknown asset {a}.")
                ok = False
            elif not assets[a].available:
                conflicts.append(f"Pin '{pin_desc}': {a} is marked out of service.")
                ok = False
            elif (a, c) not in z_set:
                barred = disallowed.get(a, set())
                bundle = bundles.get(c, {})
                if bundle and barred.issuperset(bundle.keys()):
                    conflicts.append(f"Pin '{pin_desc}': {a} can't carry any of {label}'s "
                                     "bundle options (all barred by asset restrictions).")
                else:
                    conflicts.append(f"Pin '{pin_desc}': {a} can't reach {label} "
                                     "(directly or with any available refueler).")
                ok = False
            elif not fits_cycle(a, c):
                conflicts.append(f"Pin '{pin_desc}': the {a} round trip takes "
                                 f"{trip_time[a][c]:.0f}h, which doesn't fit the "
                                 f"{cycle:g}-hour cycle.")
                ok = False
            elif row.source_warehouse_id and assets[a].home_warehouse_id != row.source_warehouse_id:
                conflicts.append(f"Pin '{pin_desc}': {a} is based at "
                                 f"{assets[a].home_warehouse_id}, not {row.source_warehouse_id}.")
                ok = False

        if row.refueler_id:
            f = row.refueler_id
            if not row.asset_id:
                conflicts.append(f"Pin '{pin_desc}': a refueler pin needs an asset pinned too.")
                ok = False
            elif f not in refuelers:
                conflicts.append(f"Pin '{pin_desc}': unknown refueler {f}.")
                ok = False
            elif not refuelers[f].available:
                conflicts.append(f"Pin '{pin_desc}': {f} is marked out of service.")
                ok = False
            elif (row.asset_id, c, f) not in p_set:
                conflicts.append(f"Pin '{pin_desc}': {f} can't make the rendezvous "
                                 f"for {row.asset_id} → {label}.")
                ok = False

        if row.package_type_id:
            k = row.package_type_id
            if k not in bundles[c]:
                conflicts.append(f"Pin '{pin_desc}': {k} is not one of {label}'s bundle options.")
                ok = False
            elif row.asset_id and k in disallowed.get(row.asset_id, set()):
                conflicts.append(f"Pin '{pin_desc}': {row.asset_id} is not able to carry {k}.")
                ok = False
            elif not row.asset_id:
                # no asset pinned: at least one reaching, in-cycle asset
                # (matching the pinned source, if any) must be able to carry it
                carriers = [
                    a for (a, cc) in z_set
                    if cc == c and fits_cycle(a, c)
                    and k not in disallowed.get(a, set())
                    and (not row.source_warehouse_id or assets[a].home_warehouse_id == row.source_warehouse_id)
                ]
                if not carriers:
                    conflicts.append(f"Pin '{pin_desc}': no available asset that can reach "
                                     f"{label} within the cycle is able to carry {k}.")
                    ok = False

        if row.source_warehouse_id:
            w = row.source_warehouse_id
            if w not in ctx["warehouses"]:
                conflicts.append(f"Pin '{pin_desc}': unknown warehouse {w}.")
                ok = False
            elif not row.asset_id:
                from_w = [(a, cc) for (a, cc) in z_set if cc == c
                          and assets[a].home_warehouse_id == w]
                if not from_w:
                    conflicts.append(f"Pin '{pin_desc}': no available asset at {w} can reach {label}.")
                    ok = False

        if ok and row.source_warehouse_id and row.source_warehouse_id in ctx["warehouses"]:
            w = row.source_warehouse_id
            reaching_assets_at_w = [
                a for (a, cc) in z_set
                if cc == c and fits_cycle(a, c) and assets[a].home_warehouse_id == w
                and (not row.asset_id or a == row.asset_id)
            ]
            if reaching_assets_at_w:
                carriable_options = {
                    k for a in reaching_assets_at_w for k in bundles.get(c, {})
                    if k not in disallowed.get(a, set())
                }
                stocked = {k for k in carriable_options if ctx["inventory"].get((w, k), 0) > 0}
                if carriable_options and not stocked:
                    conflicts.append(f"Pin '{pin_desc}': {w} has no stock of any bundle option "
                                     f"that a reaching, in-cycle asset based there could carry "
                                     f"to {label}.")
                    ok = False

        if not ok:
            continue

        pins["y"].add(c)
        if row.asset_id:
            pins["z"].add((row.asset_id, c))
        if row.refueler_id:
            pins["p"].add((row.asset_id, c, row.refueler_id))
        if row.package_type_id:
            pins["s"].add((c, row.package_type_id))
        if row.source_warehouse_id and not row.asset_id:
            pins["source"][c] = row.source_warehouse_id
        pins["rows"].append({"id": row.id, "description": pin_desc})

    # cap check counts pinned *missions* (distinct asset+customer dispatches),
    # not pinned customers — a customer pinned to two different assets is two
    # missions, and a customer pinned without an asset is (at least) one.
    customers_with_asset_pin = {c for (a, c) in pins["z"]}
    customers_without_asset_pin = pins["y"] - customers_with_asset_pin
    pinned_mission_count = len(pins["z"]) + len(customers_without_asset_pin)
    if pinned_mission_count > daily_cap:
        conflicts.append(f"{pinned_mission_count} pinned missions exceed the daily cap of "
                         f"{daily_cap} — raise the cap or remove pins.")

    return pins, conflicts


def _build_model(ctx, daily_cap, quotas, z_candidates, p_candidates, eligible, pins):
    """Builds the shared MILP structure (every constraint that's the same
    regardless of objective mode) with no objective set yet. Returns the
    model and the variable dicts, keyed by the real (asset, customer, ...)
    tuples — LP variable *names* are enumerated indices only (z_0, x_17,
    ...), never the user-editable entity IDs, so IDs containing spaces,
    dashes, or other punctuation can never collide after PuLP's name
    sanitization."""
    customers, assets, refuelers = ctx["customers"], ctx["assets"], ctx["refuelers"]
    package_types, bundles = ctx["package_types"], ctx["bundles"]
    disallowed, inventory = ctx["disallowed"], ctx["inventory"]
    reach, trip_time = ctx["reach"], ctx["trip_time"]
    settings = ctx["settings"]

    model = pulp.LpProblem("page5_daily_cap", pulp.LpMaximize)
    z = {(a, c): pulp.LpVariable(f"z_{i}", cat="Binary") for i, (a, c) in enumerate(z_candidates)}
    p = {(a, c, f): pulp.LpVariable(f"p_{i}", cat="Binary") for i, (a, c, f) in enumerate(p_candidates)}
    y = {c: pulp.LpVariable(f"y_{i}", cat="Binary") for i, c in enumerate(eligible)}

    x = {}
    x_i = 0
    for (a, c) in z_candidates:
        barred = disallowed.get(a, set())
        for k, qty_needed in bundles[c].items():
            if k in barred:
                continue
            x[(a, c, k)] = pulp.LpVariable(f"x_{x_i}", lowBound=0, upBound=qty_needed, cat="Integer")
            x_i += 1

    # time budget per asset
    for a in assets:
        terms = [trip_time[a][c] * z[(a, c)] for c in eligible if (a, c) in z]
        if terms:
            model += pulp.lpSum(terms) <= settings.cycle_hours

    # weight / volume tied to dispatch, AND dispatch tied to cargo (both
    # directions): a mission can't be "dispatched" carrying nothing (M1 —
    # phantom missions that only exist to game a quota), and cargo can't
    # exist without a dispatch to carry it (M2 — a zero-weight/zero-volume
    # package type would otherwise let x float free of z entirely, since the
    # weight/volume cap constraint below is vacuous when weight=volume=0).
    for (a, c) in z_candidates:
        x_terms = [x[(a, c, k)] for k in bundles[c] if (a, c, k) in x]
        w_terms = [package_types[k].weight * x[(a, c, k)] for k in bundles[c] if (a, c, k) in x]
        v_terms = [package_types[k].volume * x[(a, c, k)] for k in bundles[c] if (a, c, k) in x]
        spec = ctx["method_specs"][assets[a].method]
        if w_terms:
            model += pulp.lpSum(w_terms) <= spec.weight_cap * z[(a, c)]
        if v_terms:
            model += pulp.lpSum(v_terms) <= spec.vol_cap * z[(a, c)]
        if x_terms:
            model += z[(a, c)] <= pulp.lpSum(x_terms)
        else:
            model += z[(a, c)] == 0
    for (a, c, k), var in x.items():
        qty_needed = bundles[c][k]
        model += var <= qty_needed * z[(a, c)]

    # warehouse inventory
    for w_id in ctx["warehouses"]:
        assets_at_w = [a for a, av in assets.items() if av.home_warehouse_id == w_id]
        for k in package_types:
            terms = [x[(a, c, k)] for a in assets_at_w for c in eligible if (a, c, k) in x]
            if terms:
                model += pulp.lpSum(terms) <= inventory.get((w_id, k), 0)

    # bundle satisfaction: bundle lines are alternatives, not a checklist —
    # fully delivering any one option's quantity satisfies the customer.
    # s[(c, k)] = 1 iff option k is completely delivered to customer c.
    s = {}
    s_i = 0
    for c in y:
        for k, qty_needed in bundles[c].items():
            s[(c, k)] = pulp.LpVariable(f"s_{s_i}", cat="Binary")
            s_i += 1
            terms = [x[(a, c, k)] for a in assets if (a, c, k) in x]
            model += pulp.lpSum(terms) >= qty_needed * s[(c, k)]
        model += y[c] <= pulp.lpSum(s[(c, k)] for k in bundles[c])

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
        trips = [p[(a, c, ff)] for (a, c, ff) in p_candidates if ff == f]
        if trips:
            model += pulp.lpSum(trips) <= 1

    # global daily mission cap
    if z:
        model += pulp.lpSum(z.values()) <= daily_cap, "daily_delivery_cap"

    # mission-allocation-by-customer-type quotas:
    # missions to type T  >=  target_pct * missions scheduled overall
    all_z_terms = list(z.values())
    for ct_id, pct in quotas.items():
        customers_of_type = [c_id for c_id in eligible if customers[c_id].customer_type_id == ct_id]
        type_terms = [z[(a, c)] for (a, c) in z_candidates if c in customers_of_type]
        model += (
            pulp.lpSum(type_terms) >= pct * pulp.lpSum(all_z_terms),
            f"quota_{ct_id}",
        )

    # human pins — hard constraints, never silently dropped
    for c in pins["y"]:
        model += y[c] == 1
    for (a, c) in pins["z"]:
        model += z[(a, c)] == 1
    for (a, c, f) in pins["p"]:
        model += p[(a, c, f)] == 1
    for (c, k) in pins["s"]:
        model += s[(c, k)] == 1
    for c, w_id in pins["source"].items():
        for (a, cc) in z_candidates:
            if cc == c and assets[a].home_warehouse_id != w_id:
                model += z[(a, cc)] == 0

    return model, z, x, y, s, p


def _extract_result(model, z, x, y, s, p, ctx, z_candidates, eligible, pins):
    """Common result-shaping tail, shared by every objective mode (single
    weighted-sum solves and each pass of the lexicographic solve alike)."""
    customers, assets, refuelers = ctx["customers"], ctx["assets"], ctx["refuelers"]
    bundles = ctx["bundles"]
    customer_types = ctx["customer_types"]

    status = pulp.LpStatus[model.status]
    time_limited = _is_time_limited(model)

    if status != "Optimal":
        result = {
            "status": status, "deliveries_scheduled": 0, "satisfied_count": 0,
            "satisfied_ranks": [], "mission_counts_by_type": {},
            "customers": [], "dispatches": [], "time_limited": time_limited,
        }
        if status == "Infeasible" and pins["rows"]:
            descs = [r["description"] for r in pins["rows"]]
            result["infeasible_hint"] = (
                "The model came back infeasible with pins active — the pins below are "
                "the likely interaction; remove or relax one and re-run to confirm: "
                + "; ".join(descs)
            )
        return result

    def val(var):
        # PuLP can return values like 2.9999999997 or -1e-9 for integer/
        # binary variables; round before truncating so we never silently
        # drop a unit or read a spurious dispatch off floating-point noise.
        return int(round(pulp.value(var) or 0))

    dispatches = []
    for (a, c) in z_candidates:
        if val(z[(a, c)]) > 0:
            shipped = {k: val(x[(a, c, k)]) for k in bundles[c]
                       if (a, c, k) in x and val(x[(a, c, k)]) > 0}
            paired = [f for f in refuelers if (a, c, f) in p and val(p[(a, c, f)]) > 0]
            dispatches.append({
                "asset_id": a, "home_warehouse_id": assets[a].home_warehouse_id, "method": assets[a].method,
                "customer_id": c, "refueler_id": paired[0] if paired else None, "cargo": shipped,
                "pinned": (a, c) in pins["z"] or c in pins["y"],
            })

    # per-type mission counts, for verifying the quota visually on the frontend
    type_counts = {}
    for d in dispatches:
        c_id = d["customer_id"]
        ct_id = customers[c_id].customer_type_id
        type_name = customer_types[ct_id].name if ct_id in customer_types else "Unassigned"
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    customer_results = []
    for c_id, cust in sorted(customers.items(), key=lambda kv: kv[1].priority_rank):
        if c_id not in y:
            continue
        satisfied = val(y[c_id]) > 0
        satisfied_by = None
        shortfall = {}
        if satisfied:
            satisfied_by = next((k for k in bundles[c_id]
                                 if (c_id, k) in s and val(s[(c_id, k)]) > 0), None)
        else:
            # no option completed — show how far each one got
            for k, qty_needed in bundles[c_id].items():
                shipped = sum(val(x[(a, c_id, k)]) for a in assets if (a, c_id, k) in x)
                if shipped < qty_needed:
                    shortfall[k] = {"needed": qty_needed, "shipped": shipped}
        type_name = customer_types[cust.customer_type_id].name if cust.customer_type_id in customer_types else None
        customer_results.append({
            "customer_id": c_id, "label": cust.label, "rank": cust.priority_rank,
            "customer_type": type_name, "satisfied": satisfied,
            "satisfied_by": satisfied_by, "shortfall": shortfall,
            "pinned": c_id in pins["y"],
        })

    satisfied_ranks = sorted(r["rank"] for r in customer_results if r["satisfied"])
    return {
        "status": status,
        "deliveries_scheduled": len(dispatches),
        "satisfied_count": len(satisfied_ranks),
        "satisfied_ranks": satisfied_ranks,
        "mission_counts_by_type": type_counts,
        "customers": customer_results,
        "dispatches": dispatches,
        "time_limited": time_limited,
    }


def _solve_single_objective(ctx, daily_cap, weights, quotas, z_candidates, p_candidates,
                             eligible, pins, time_limit):
    """One MILP solve with a single weighted-sum objective (max_count,
    rank_weighted)."""
    model, z, x, y, s, p = _build_model(ctx, daily_cap, quotas, z_candidates, p_candidates,
                                        eligible, pins)
    model.objective = pulp.lpSum(weights[c] * y[c] for c in y)
    model.objective.name = "objective"
    model.solve(_get_solver(time_limit))
    return _extract_result(model, z, x, y, s, p, ctx, z_candidates, eligible, pins)


def _solve_lexicographic(ctx, daily_cap, quotas, z_candidates, p_candidates, eligible, pins,
                          time_limit):
    """True sequential lexicographic solve for strict_priority: walk
    distinct priority_rank groups from best (1) to worst, maximizing each
    group's satisfied count in turn and freezing the achieved count as a
    hard constraint before moving on, so a higher-ranked customer can never
    be traded away for any number of lower-ranked ones — exact at any
    customer count, unlike the old exponential-weight approximation (which
    silently breaks once weights overflow, around ~40 customers). A final
    pass maximizes the total satisfied count subject to every group's
    frozen floor, to pick up any remaining slack the group-by-group passes
    left on the table."""
    model, z, x, y, s, p = _build_model(ctx, daily_cap, quotas, z_candidates, p_candidates,
                                        eligible, pins)
    customers = ctx["customers"]

    groups = defaultdict(list)
    for c in eligible:
        groups[customers[c].priority_rank].append(c)
    ranks = sorted(groups)  # 1 = highest priority, solved first

    solver = _get_solver(time_limit)
    any_time_limited = False

    for rank in ranks:
        group = groups[rank]
        model.objective = pulp.lpSum(y[c] for c in group)
        model.objective.name = f"lex_rank_{rank}"
        model.solve(solver)
        status = pulp.LpStatus[model.status]
        if status != "Optimal":
            # Shouldn't happen — y=0 for everyone always satisfies every
            # constraint built so far — but if it does, surface the honest
            # status rather than pretending a later pass could recover.
            return _extract_result(model, z, x, y, s, p, ctx, z_candidates, eligible, pins)
        any_time_limited = any_time_limited or _is_time_limited(model)
        achieved = int(round(pulp.value(model.objective) or 0))
        model += pulp.lpSum(y[c] for c in group) >= achieved, f"lex_freeze_rank_{rank}"

    # final pass: use any remaining slack to maximize total satisfied count,
    # without disturbing any rank group's already-frozen achieved count
    model.objective = pulp.lpSum(y[c] for c in eligible)
    model.objective.name = "lex_final_total"
    model.solve(solver)
    any_time_limited = any_time_limited or _is_time_limited(model)

    result = _extract_result(model, z, x, y, s, p, ctx, z_candidates, eligible, pins)
    result["time_limited"] = bool(result.get("time_limited")) or any_time_limited
    return result


def solve_daily_cap(db, daily_cap: int, quotas=None) -> dict:
    """Solve the day's schedule under every objective mode.
    quotas: list of {customer_type_id, target_pct} from the request, or None
    to fall back to the stored Mission Allocation Policies."""
    ctx = get_context(db)
    customers = ctx["customers"]
    customer_types = ctx["customer_types"]

    if quotas is None:
        quota_map = {p.customer_type_id: p.target_pct for p in ctx["allocation_policies"].values()}
    else:
        quota_map = {q.customer_type_id: q.target_pct for q in quotas if q.target_pct > 0}

    eligible = [c for c in customers if ctx["bundles"].get(c) and customers[c].included]
    z_candidates, p_candidates = _build_candidates(ctx, eligible)
    pins, conflicts = _validate_pins(ctx, eligible, set(z_candidates), set(p_candidates), daily_cap)

    excluded = [c for c in customers if not customers[c].included]
    out_of_service = ([a for a, av in ctx["assets"].items() if not av.available]
                      + [f for f, fv in ctx["refuelers"].items() if not fv.available])

    base = {
        "daily_cap": daily_cap,
        "customers_total": len(eligible),
        "excluded_customers": excluded,
        "out_of_service": out_of_service,
        "pins_applied": pins["rows"],
        "pin_conflicts": conflicts,
        "data_warnings": ctx.get("data_warnings", []),
        "quotas_applied": [
            {"customer_type_id": ct_id,
             "name": customer_types[ct_id].name if ct_id in customer_types else str(ct_id),
             "target_pct": pct}
            for ct_id, pct in quota_map.items()
        ],
    }

    if conflicts:
        # human decisions are never silently overridden — refuse and explain
        logger.info("[solver] refusing to solve: %d pin conflicts", len(conflicts))
        return {**base, "modes": []}

    time_limit = _time_limit_s()
    logger.info("[solver] daily_cap=%s, %d customers in play, %d pins, quotas=%s, "
                "time_limit=%ss, solving %d objective modes",
                daily_cap, len(eligible), len(pins["rows"]), quota_map, time_limit,
                len(OBJECTIVE_MODES))

    modes = []
    with _solve_lock:
        for key, label, description in OBJECTIVE_MODES:
            if key == "strict_priority":
                result = _solve_lexicographic(ctx, daily_cap, quota_map, z_candidates,
                                              p_candidates, eligible, pins, time_limit)
            else:
                weights = _weights_for_mode(key, customers, eligible)
                result = _solve_single_objective(ctx, daily_cap, weights, quota_map, z_candidates,
                                                  p_candidates, eligible, pins, time_limit)
            logger.info("[solver] mode=%s status=%s satisfied=%s missions=%s time_limited=%s",
                        key, result["status"], result["satisfied_count"],
                        result["deliveries_scheduled"], result.get("time_limited"))
            modes.append({"mode": key, "label": label, "description": description, **result})

    return {**base, "modes": modes}
