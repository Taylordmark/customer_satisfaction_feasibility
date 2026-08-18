# Delivery Feasibility Assessment — Project Scenario

## The premise

An organization runs a distribution network: **warehouses** hold **package
inventory**, **transport assets** (aircraft, trucks, ships) carry packages
from warehouses to **customers**, and **refuelers** extend an asset's range
when a customer is farther out than the asset can reach on its own fuel.
Carrying ability is **per-vehicle**, not per transport method — one ship may
be able to take a package another ship can't. Every asset is owned by a
**transport control team** — the organization that has tasking authority
over it. Every customer has a **bundle of package options** — the options
are alternatives, and fully delivering any one of them satisfies the
customer — and customers are **priority-ranked 1-n** (1 = highest; the
optimizer converts rank r of N to weight N+1−r). Only a limited number of delivery
**missions** can be scheduled in a day, and leadership may want a guaranteed
**minimum share of missions** to go to a particular customer type (e.g. "at
least 40% of missions go to Storefront-type customers").

The question this project answers, end to end: **given everything above, who
can actually get resupplied, by whom, from where, and how many missions does
it take?**

## How the model evolved

This started as a plain linear program and grew in stages, each one adding a
constraint that turned out to matter in practice:

1. **Priority-weighted allocation** — customers get a blended priority score
   (local weight + HQ weight), and the objective maximizes priority-weighted
   satisfaction rather than raw volume moved.
2. **Geography** — nodes and customers got real lat/lon coordinates, and
   distance became a haversine calculation rather than an assumption.
3. **Bundles, not units** — a customer isn't "50% satisfied" by getting half
   their order. Satisfaction became binary and all-or-nothing per customer,
   which turned the LP into a MILP.
4. **Asset range + refueling** — assets are point-to-point (launch, deliver,
   return to reload) with a hard range. When a destination is out of range,
   a refueler can extend it — but only if the refueler can physically reach
   a computed rendezvous point along the route, and only a limited number of
   refuelers exist. Refuelers no longer need to share a home base with the
   asset they meet.
5. **A 24-hour execution cycle** — every asset gets a flying-hour budget per
   day instead of an assumed single trip. This is the single most consequential
   constraint in the whole model: it revealed that Sea assets can't complete
   an ocean crossing in a day, and that cargo restrictions (hazmat/sensitive
   packages barred from Air) collide with the *only* transport method fast
   enough to fit inside 24 hours — stranding some customers structurally,
   not for lack of capacity.
6. **Multi-day horizons** — asset time budgets and refueler availability
   reset every day; inventory and bundle progress carry forward across days.
7. **Tasking authority** — assets aren't just physically capable, they're
   *owned*. A transport control team must actually agree to task their asset
   before a delivery happens. This added an organizational layer on top of
   the physical feasibility layer.
8. **Mission allocation quotas** — leadership doesn't only care about total
   throughput; they may want a guaranteed floor of missions going to a given
   customer type, expressed as a percentage of that day's schedule.
9. **Options, not checklists** — bundle lines changed meaning: instead of
   every line being required, the lines are now alternatives, and fully
   delivering any one option's quantity satisfies the customer. The solver
   picks which option; satisfaction is still all-or-nothing per option.
10. **Per-vehicle carrying ability** — cargo restrictions moved from the
    transport method to the individual asset. "Air can't carry hazmat" became
    a per-aircraft property, so a fleet can contain a certified vehicle even
    when its siblings are barred.
11. **Rank-based priority and comparable objectives** — the blended w/h score
    became an explicit 1-n priority rank, and every schedule run now solves
    the model under three objectives side by side: most customers satisfied
    (all equal), rank-weighted (rank converts to linear weight), and highest
    ranks first (exponential weights make rank strictly lexicographic). The
    per-type mission share floors moved onto the generate page as inputs,
    with the stored policies as defaults.
12. **A human decision layer** — the optimizer stopped being the only
    decision-maker. Customers can be excluded from today's plan (page 1),
    vehicles and refuelers toggled out of service (pages 2 and 4), and
    missions pinned in advance at any level of detail — just a customer
    ("must satisfy today"), a customer + asset, a tanker pairing, a bundle
    option, or a source warehouse (pages 3-5 and the Planned Missions
    admin tab). Pins are hard constraints that count against the cap and
    quotas; whatever is left unspecified stays the optimizer's choice. A
    conflicting pin (out-of-range asset, trip that can't fit the cycle,
    more pins than cap) makes the run refuse with a per-pin explanation
    instead of being silently dropped. Vehicles also carry a model name
    (Albatross HL, Manta-class, ...) and page 4 rolls the fleet up to a
    count per vehicle type at each location.

## From spreadsheet-style scripts to a real tool

The model was originally a set of standalone Python scripts (data generator
+ PuLP solver) run by hand, iterated on conversationally. This repo turns
that into an actual application:

- **Every input is now editable through the UI**, not hardcoded — warehouses,
  teams, customer types, customers, package types, transport methods,
  per-vehicle cargo restrictions, assets, refuelers, inventory, bundles, and
  the cycle-wide solver settings all live in a database and are fully
  editable through the tabbed Data section.
- **The feasibility assessment is a guided, five-page drill-down** rather
  than a single solver run, so a person can see *why* something is or isn't
  possible at each layer, not just the final answer:

  | Page | Question it answers |
  |---|---|
  | 1 | What package options would satisfy each customer (any one is enough)? |
  | 2 | Which individual vehicles are even able to carry those packages? |
  | 3 | Which warehouses have both the stock and an in-range (or refuelable) transport? |
  | 4 | What support does the delivery need — which vehicles only get there with a refueler, and which tankers can provide it? (The controlling team is shown per vehicle — tasking authority follows from the location/vehicle combination.) |
  | 5 | Given a cap on missions per day and per-type mission share floors, how many can be scheduled — solved under three objectives (most satisfied / rank-weighted / highest ranks first) for the user to compare and choose. |

  Pages 1–4 are progressively-filtered views over the same live data. Page 5
  is the only one that runs the actual MILP solve — it re-solves on demand
  against whatever the daily mission cap is set to, live, using the current
  database contents.

## Architecture

```
feasibility-app/
├── backend/            FastAPI + SQLAlchemy + SQLite, PuLP solver
│   └── app/
│       ├── models.py        the full editable schema
│       ├── feasibility.py   pages 1-4: reachability, bundles, support
│       ├── solver.py        page 5: live MILP solve with quotas + daily cap
│       ├── seed.py          example dataset, loaded once if DB is empty
│       └── routers/         generic CRUD + the 5 feasibility endpoints
├── frontend/           React (Vite) — sidebar nav, 5 assessment pages,
│                       and a tabbed data-admin section built on one
│                       generic editable-table component
└── docker-compose.yml  backend + nginx-served frontend, SQLite on a volume
```

Design choices worth knowing about:

- **Nothing is precomputed and cached.** Reachability, distance, and trip
  time are all recalculated from the database on every request. Since the
  whole point is that the data is editable, caching a stale reachability
  table would silently produce wrong answers the moment someone edits an
  asset's range or adds a warehouse.
- **The generic CRUD factory (backend) and EntityTable component (frontend)**
  exist so that adding a 13th entity later doesn't mean writing another full
  set of routes and another bespoke table UI — it's a config object away.
- **The mission-allocation quota is a linear constraint, not a post-hoc
  filter**: `missions to type T ≥ target_pct × total missions scheduled`.
  It's enforced by the solver itself, so a quota that's actually infeasible
  given the day's reachability will show up as the solver failing to hit
  100% rather than silently being ignored.

## Current status

**Backend: built and tested end-to-end.** All CRUD endpoints and all five
feasibility endpoints were exercised against a live running instance. The
seed dataset now has 24 priority-ranked customers scattered realistically
across the theater. A page-5 run at cap 8 with a 40% Storefront floor
verified the three objectives genuinely diverge: max-count fills the slots
with the cheapest orders (including ranks 21, 15, 14), while rank-weighted
and strict-priority cover ranks 2–7, 10, 11 — and rank 1 (Okinawa, whose
only accepted options are barred from every vehicle fast enough to arrive
inside the 24-hour cycle) stays structurally unsatisfiable under every
objective, which is exactly the diagnosis pages 1–4 exist to explain. The
solver probes PuLP's bundled CBC binary at first use and falls back to
HiGHS on hosts where it can't execute (e.g. arm64 macs without Rosetta).

**Frontend: built and verified in-browser.** All five assessment pages
render against live data, the page-5 slider/re-solve loop works, and a
data-admin edit round-trips through the UI to the database and back.

**Deployment: done and verified.** `docker compose up` builds and runs the
full stack — FastAPI backend container plus an nginx container that serves
the built SPA (with client-side-route fallback) and reverse-proxies `/api`
to the backend. SQLite lives on a named volume, so data survives rebuilds.
The app is served on host port 8080. The full solve was re-verified through
the containerized stack.

**Local dev:** backend `uvicorn app.main:app` with `DB_PATH` pointing at a
writable path (the default `/data/app.db` is the container path), frontend
`npm run dev` (Vite proxies `/api`; set `VITE_API_PROXY_TARGET` if the
backend isn't on `localhost:8000`).

## Model assumptions

These are simplifications baked into the current feasibility/solver model.
None of them are bugs — they're deliberate scope cuts — but they mean the
numbers are directionally right, not a precise fuel/time simulation. Listed
here so anyone reading a result knows what it does and doesn't account for:

- **Range is a one-way radius; trip time is round-trip.** A method's
  `range_mi` gates reachability as a straight-line distance from the home
  warehouse to the customer (`distance <= range_mi`), but the scheduled
  trip time charges `2 * distance / speed_mph` — i.e. the model assumes the
  asset can always physically get back, it just doesn't reserve any extra
  *range* for the return leg. This also applies to refueled trips: the
  tanker rendezvous point is computed on the outbound leg only (at
  `range_mi` from home, extended by the tanker's `extension_mi`), so a
  refueled asset's return leg is unmodeled fuel-wise even though its return
  *time* is still counted.
- **Refueler transit and return are unmodeled.** A tanker's own trip out to
  the rendezvous point is checked for feasibility (its `self_range_mi` must
  cover the distance from its home warehouse to the rendezvous point), but
  that transit contributes no time to the schedule, and the tanker's return
  trip home isn't modeled at all. Refueling instead adds a single flat
  `refuel_overhead_hours` to the mission's trip time regardless of how far
  the tanker actually had to fly.
- **One rendezvous per tanker per day.** Each refueler can support at most
  one asset-customer pairing per solve, no matter how short any individual
  rendezvous would be — it can't be reused for a second mission the same
  cycle.
- **Dispatch is binary, so an asset makes at most one trip per customer per
  day.** The solver's per-(asset, customer) dispatch variable is 0/1, not a
  count — an asset can't make two round trips to the same customer in one
  cycle even if the numbers would allow it. A customer bundle too large for
  any single asset's capacity can still be met, but only by splitting the
  delivery across *multiple different assets*, not by one asset making
  repeat runs.
- **Page 5 solves a single day.** Everything here — cap, quotas, pins,
  reachability — is scoped to one `cycle_hours` period. There's no
  multi-day carryover, backlog, or lookahead; a customer left unsatisfied
  today doesn't affect tomorrow's run. Multi-day scheduling was scoped for
  a later stage (stage 6) and isn't implemented by this solver.
