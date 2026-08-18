# Delivery Feasibility Assessment — Project Scenario

## The premise

An organization runs a distribution network: **warehouses** hold **package
inventory**, **transport assets** (aircraft, trucks, ships) carry packages
from warehouses to **customers**, and **refuelers** extend an asset's range
when a customer is farther out than the asset can reach on its own fuel.
Every asset is owned by a **transport control team** — the organization that
has tasking authority over it. Every customer needs a specific **bundle** of
package types and quantities to be considered satisfied, and different
customers carry different **priority**. Only a limited number of delivery
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

## From spreadsheet-style scripts to a real tool

The model was originally a set of standalone Python scripts (data generator
+ PuLP solver) run by hand, iterated on conversationally. This repo turns
that into an actual application:

- **Every input is now editable through the UI**, not hardcoded — warehouses,
  teams, customer types, customers, package types, transport methods and
  their cargo restrictions, assets, refuelers, inventory, and bundles all
  live in a database and are fully CRUD-manageable.
- **The feasibility assessment is a guided, five-page drill-down** rather
  than a single solver run, so a person can see *why* something is or isn't
  possible at each layer, not just the final answer:

  | Page | Question it answers |
  |---|---|
  | 1 | What packages, and how many, would satisfy each customer? |
  | 2 | What transport methods are even able to carry those packages? |
  | 3 | Which warehouses have both the stock and an in-range (or refuelable) transport? |
  | 4 | Which transport control teams actually own those capable assets — who do you need to coordinate with? |
  | 5 | Given a cap on missions per day (and any allocation quotas), how many can actually be scheduled? |

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
│       ├── feasibility.py   pages 1-4: reachability, bundles, ownership
│       ├── solver.py        page 5: live MILP solve with quotas + daily cap
│       ├── seed.py          example dataset, loaded once if DB is empty
│       └── routers/         generic CRUD + the 5 feasibility endpoints
├── frontend/           React (Vite) — sidebar nav, 5 assessment pages,
│                       and a tabbed data-admin section built on one
│                       generic editable-table component
└── docker-compose.yml  (pending — see status below)
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
feasibility endpoints were exercised against a live running instance,
including a full page-5 solve that correctly reproduced the earlier
hand-verified result (2 customers satisfied, 2 structurally blocked by the
Air-cargo-restriction / 24-hour-cycle collision described above).

**Frontend: built, not yet verified.** The React app, the generic data
table, and all five page components are written but `npm install` / a real
build/render pass has not been run yet.

**Not yet done:** Dockerfiles (backend + frontend), nginx reverse-proxy
config, `docker-compose.yml`, and a final end-to-end pass with everything
running together.
