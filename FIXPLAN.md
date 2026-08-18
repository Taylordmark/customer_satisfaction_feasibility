# Fix Plan — Solver Math & Interface Audit (2026-08-18)

Remediation plan for the production audit findings (finding IDs M1–M11, I1–I7 refer
to the audit report). Ordered so the math is provably correct first; each phase
lists exact files, the change, and how it's verified. Auth/user management is out
of scope, per the audit.

**Critical path to "math is prod-safe": Phases 0–4 (~3–4 days). Full plan: ~2 weeks.**

---

## Phase 0 — Regression harness (do first, everything else proves itself against it)

The audit's five probes are ready-made failing tests. No fix lands before the test
that catches its bug exists.

- [x] `backend/requirements-dev.txt`: `pytest`, `httpx` (for API-level tests).
- [x] `backend/tests/conftest.py`: set `DB_PATH` to a tmp path **before** importing
      `app.*` (database.py reads it at import time), fixture that runs
      `Base.metadata.create_all` + `seed_if_empty`, yields a session, tears down.
- [x] `backend/tests/test_audit_regressions.py` — port the five probes:
      1. 70% FOB quota at cap 8 → assert **no dispatch has empty cargo** (M1).
      2. Zero-weight/volume package → assert the write is rejected 422; and with a
         hand-inserted legacy bad row, assert no customer is satisfied without a
         dispatch (M2).
      3. `priority_rank=40` of 24 → assert the customer IS satisfied at slack cap
         under rank_weighted (M3).
      4. `speed_mph=0` → assert write rejected 422; legacy bad row → pages 3–5
         return results (asset skipped), not a 500 (M4).
      5. Two source pins for one customer → assert a pin conflict is reported (M5).

All five fail on main today. Phases 1–4 turn them green one by one.

## Phase 1 — Missing solver link: missions must carry cargo (M1, M9, M10)

`backend/app/solver.py`

- [x] **M1a — prune impossible candidates**: in `_build_candidates`, skip `(a, c)`
      when the asset is barred from *every* option in `bundles[c]` (today it can be
      "dispatched" but only ever fly empty). Needs `bundles`/`disallowed` from ctx.
- [x] **M1b — tie dispatch to cargo**: in `_solve_one`, for each candidate add
      `z[(a,c)] <= lpSum(x[(a,c,k)] for k)`. Kills phantom quota-gaming missions.
- [x] **M1c — pin message**: `(a, c) not in z_set` conflict text currently says
      "can't reach" — after pruning it can also mean "can't carry any bundle
      option"; update the message to name whichever is true.
- [x] **M9 — extraction**: replace `int(pulp.value(v))` with
      `int(round(pulp.value(v) or 0))` everywhere values are read out.
- [x] **M10 — variable names**: name variables by enumerated index
      (`z_0, z_1, …`), keep the `(a,c)`→var dict as the only mapping. User IDs
      never enter LP names, so `"C 1"` / `"C_1"` can't collide.
- [x] Tests: probe 1 goes green; new unit test with IDs containing spaces/dashes.

## Phase 2 — Input validation on math-critical fields (M2, M3, M4, feeds I4)

`backend/app/schemas.py` — add `Field` constraints (writes only; defense-in-depth
below covers pre-existing rows):

- [x] PackageType: `weight: gt=0`, `volume: gt=0`
- [x] MethodSpec: `speed_mph: gt=0`, `weight_cap: gt=0`, `vol_cap: gt=0`, `range_mi: gt=0`
- [x] Refueler: `extension_mi: ge=0`, `self_range_mi: ge=0`
- [x] WarehouseInventory: `qty: ge=0`; CustomerBundleItem: `qty_needed: ge=1`
- [x] Customer: `priority_rank: ge=1`, lat `[-90, 90]`, lon `[-180, 180]`; Warehouse lat/lon same
- [x] MissionAllocationPolicy + QuotaInput: `target_pct: gt=0, le=1`
- [x] Settings: `cycle_hours: gt=0`, `handling_time_hours: ge=0`,
      `refuel_overhead_hours: ge=0`, `default_daily_cap: ge=1`
- [x] SolveRequest: `daily_cap: ge=1`

Defense in depth for rows that predate validation:

- [x] `solver._weights_for_mode`: rank-weighted weight becomes `max(1, n+1-rank)` (M3).
- [x] `feasibility.compute_reachability`: treat a spec with `speed_mph <= 0` or
      `range_mi <= 0` as unable to reach anything (skip, don't divide); collect
      the skipped asset IDs into `ctx["data_warnings"]` and include them in the
      page-5 response so the problem is visible, not silent (M4).
- [x] Tests: probes 2–4 green; 422 assertions for each bad write.

## Phase 3 — Solver robustness (M6, M7)

`backend/app/solver.py`

- [x] **M6 — time limit**: read `SOLVER_TIME_LIMIT_S` (env var, default 60) and
      pass as `timeLimit` to `PULP_CBC_CMD` / `HiGHS`. Env var, **not** a Settings
      column: `create_all` won't ALTER an existing table, and there's no migration
      tooling — adding a Settings column would silently break existing volumes.
- [x] **M6b — status surfacing**: verify empirically how PuLP maps
      stopped-on-time-with-incumbent for both CBC and HiGHS (write the test with a
      tiny limit); report it as `"time_limited": true` per mode, distinct from
      Infeasible. Frontend: distinct badge ("best found within limit").
- [x] **M6c — concurrency**: module-level `threading.Lock` around the 3-mode solve
      loop so concurrent Run clicks queue instead of stacking CBC processes.
- [x] **M7 — true lexicographic strict-priority**: replace the 2^n weight trick
      with sequential solves — walk rank groups from priority 1 down; for each
      group maximize that group's satisfied count, then freeze it as a constraint
      (`lpSum(y_g) >= achieved`) and continue. ~one fast solve per distinct rank,
      all under the shared time limit. Exact at any customer count; the doubling
      trick silently breaks past ~40 customers.
- [x] Tests: crafted case where a top-rank customer conflicts with two lower ones →
      top rank always wins; 60-customer synthetic case solves correctly.

## Phase 4 — Pin-conflict completeness (M5, M8)

`backend/app/solver.py:_validate_pins`

- [x] **M5 — duplicate source pins**: >1 distinct `source_warehouse_id` pinned for
      one customer → conflict (today the dict silently keeps only the last).
- [x] Duplicate *option* pins for one customer → conflict too (forcing two options
      to full delivery is almost certainly not what the user meant).
- [x] **M8a — uncarriable option pin**: option pinned without an asset, but no
      reaching-and-fitting asset may carry it → conflict naming the reason.
- [x] **M8b — stockless source pin**: source pinned but that warehouse has no stock
      of any option carriable by its reaching assets → conflict.
- [x] Cap check counts *missions*, not customers: distinct `(asset, customer)` pins
      plus customers pinned without an asset.
- [x] Residual: subtler pin interactions can still yield Infeasible — when that
      happens and pins exist, the response should say "likely pin interaction" and
      list the pins, instead of a bare status.
- [x] Tests: probe 5 green + one test per new conflict class.

## Phase 5 — UI error handling & forms (I1, I2)

- [x] **I2a** `frontend/src/api.js`: when `body.detail` is an array (FastAPI 422),
      format to `field: message; …` instead of `[object Object]`.
- [x] **I2b** `backend/app/routers/crud_factory.py`: translate `IntegrityError`
      before surfacing — "FOREIGN KEY" → "…references a record that doesn't
      exist", "UNIQUE" → "…already exists for that combination". Raw driver text
      goes to the log, not the user.
- [x] **I1** `frontend/src/components/EntityTable.jsx`: non-nullable selects get a
      real "— select —" placeholder option; Save validates required selects are
      chosen and marks the offending field, instead of submitting `""` as a
      foreign key. (Placeholder over auto-picking the first option: a silent
      default FK is how wrong data gets saved confidently.)
- [x] Verify in browser (no frontend test infra; not worth adding for this scope).

## Phase 6 — Page 5 run-context & quota UX (I3, I4, I7)

`frontend/src/pages/Page5Schedule.jsx`, `frontend/src/pages/DataAdmin.jsx`

- [x] **I3** Result header shows what the run used — `result.daily_cap` +
      `result.quotas_applied` (both already in the response). Mark results stale
      (banner + dimmed) when cap/quota inputs or the pin list differ from the run.
- [x] **I4a** Clamp quota inputs to 0–100 on change; red warning when floors sum
      \> 100% ("guarantees an empty schedule — types don't overlap").
- [x] **I4b** Explicit callout when a mode is Optimal with 0 missions and floors
      are active: "empty because of the mission-share floors", not a bare 0/24.
- [x] **I4c** Unify quota units on percent: DataAdmin policies tab displays and
      edits %, converting to the stored 0–1 fraction on save (add a small
      `scale` display-transform option to EntityTable columns).
- [x] **I7** `MAX_CAP` → `max(30, customers.length, settings.default_daily_cap)`.

## Phase 7 — Pages 3/4 agree with page 5 (M11)

`backend/app/feasibility.py`, `frontend/src/pages/Page3Locations.jsx`, `Page4Support.jsx`

- [x] Pages 3/4 annotate each asset/refueler with `available` and **exclude
      out-of-service vehicles from feasibility verdicts** (`feasible`,
      `needs_support`, `unreachable`) while still listing them grayed-out — the
      drill-down keeps showing physical capability, but verdicts match page 5.
- [x] Page 3 `feasible` requires `stock >= qty_needed`; add a distinct
      `partial` state for `0 < stock < qty_needed` labeled "partial — the solver
      may split across sources". Update page copy.
- [x] Tests: out-of-service-only reach → not deliverable on pages 3/4; partial
      stock → partial, not feasible.

## Phase 8 — Toggle robustness & accessibility (I5, I6)

- [x] `crud_factory`: add `PATCH /{id}` partial update (only provided fields set).
- [x] Pages 1/2/4 toggles (include, star, stand-down, tanker pin): send PATCH with
      just the changed field; disable the control while the request is in flight
      (kills the stale-object-spread lost-update race).
- [x] Replace interactive `<span>`/`<div>`s (★, ×, vehicle names, tanker badges,
      mode cards) with `<button>`s; visible `:focus-visible` style in `index.css`;
      `aria-pressed` on toggles; promote `title`-only state cues to visible text
      or `aria-label`.

## Phase 9 — Hygiene & docs

- [x] `logging` module instead of `print` (uvicorn log config picks it up).
- [x] FastAPI lifespan handler instead of deprecated `@app.on_event`.
- [x] `Session.get()` instead of legacy `Query.get()` in crud_factory.
- [x] Startup guard: create the default Settings row if missing (settings router
      and solver currently assume it exists).
- [x] CORS origins from `CORS_ORIGINS` env (default stays permissive for dev; the
      nginx proxy makes prod same-origin anyway).
- [x] `SCENARIO.md`: add a "Model assumptions" section — range is a one-way radius
      while time is round-trip; refueler time/return legs unmodeled; flat refuel
      overhead; one rendezvous per tanker per day; binary dispatch = one trip per
      asset-customer pair; page 5 is single-day (multi-day from stage 6 is not in
      this solver).

## Final verification

- [x] Full pytest suite green (all five audit regressions + per-phase tests).
- [x] Re-run the audit probe script → all five probes clean.
- [x] `docker compose up --build`; walk all five pages + a data-admin edit
      round-trip in the browser; confirm solve at cap 8 / 40% Storefront still
      reproduces the scenario doc's reference result (ranks 2–7, 10, 11; rank 1
      structurally unsatisfiable).

## Notes & risks

- **No migration tooling** — avoid new columns on existing tables (that's why the
  solver time limit is env-config, not a Settings field). If a schema change ever
  becomes necessary, add Alembic first.
- **Lexicographic mode is N solves, not 1** — bounded by the shared time limit;
  with seed-scale data it's still sub-second per solve.
- **Candidate pruning (M1a) changes some pin-conflict texts** — probe/test
  assertions must match the new wording.
- **PuLP's time-limit status mapping differs by backend** — write the M6b test
  against both CBC and HiGHS before trusting the `time_limited` flag.
