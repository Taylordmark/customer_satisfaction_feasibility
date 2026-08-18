import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import { patch } from "../patch";

function FragmentRows({ w, fleet, packageTypes, barredByAsset, busy, toggleAvailable }) {
  // Counts by vehicle_type, in first-encounter order — fleet is already sorted
  // by method then vehicle_type, so this yields the same ordering as the rows below.
  const typeCounts = [];
  const typeCountIndex = new Map();
  fleet.forEach((a) => {
    const key = `${a.method}|${a.vehicle_type}`;
    let entry = typeCountIndex.get(key);
    if (!entry) {
      entry = { vehicle_type: a.vehicle_type, count: 0 };
      typeCountIndex.set(key, entry);
      typeCounts.push(entry);
    }
    entry.count++;
  });
  return (
    <Fragment>
      <tr>
        <td colSpan={3 + packageTypes.length}
            style={{ background: "var(--panel-alt, #f0f2f7)", fontWeight: 700, fontSize: 13 }}>
          {w.label} <span className="muted" style={{ fontWeight: 400 }}>({w.id})</span>{" "}
          {typeCounts.map((c) => (
            <span key={c.vehicle_type} className="badge badge-neutral"
                  style={{ marginRight: 4, marginBottom: 3, fontWeight: 400 }}>
              {c.count}× {c.vehicle_type}
            </span>
          ))}
        </td>
      </tr>
      {fleet.map((a) => {
        const barred = barredByAsset[a.id] || new Set();
        const isBusy = !!busy[a.id];
        return (
          <tr key={a.id} style={a.available ? {} : { opacity: 0.45 }}>
            <td style={{ paddingLeft: 18 }}>
              <button
                type="button"
                className="btn-unstyled"
                onClick={() => toggleAvailable(a)}
                disabled={isBusy}
                aria-pressed={a.available}
                aria-label={`${a.id} — ${a.available ? "in service, click to stand down" : "out of service, click to return to service"}`}
                title={a.available ? "In service — click to stand down" : "Out of service — click to return to service"}
                style={{ padding: 0, margin: 0, fontWeight: 600,
                         textDecoration: a.available ? "none" : "line-through" }}
              >{a.id}</button>
            </td>
            <td className="muted" style={{ fontSize: 12.5 }}>{a.method}</td>
            <td className="muted" style={{ fontSize: 12.5 }}>{a.vehicle_type}</td>
            {packageTypes.map((pt) => (
              <td key={pt.id} style={{ textAlign: "center" }}>
                {barred.has(pt.id)
                  ? <span style={{ color: "var(--bad, #b3261e)", fontWeight: 600 }} title={`${a.id} cannot carry ${pt.name}`}>✗</span>
                  : <span style={{ color: "var(--good, #1b7f4d)", fontWeight: 600 }} title={`${a.id} can carry ${pt.name}`}>✓</span>}
              </td>
            ))}
          </tr>
        );
      })}
    </Fragment>
  );
}

export default function Page2Transports() {
  const [barredByAsset, setBarredByAsset] = useState(null); // {asset_id: Set(package ids)}
  const [packageTypes, setPackageTypes] = useState(null);
  const [assets, setAssets] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState({}); // asset_id -> bool

  async function load() {
    try {
      const [page2, pts, as, whs] = await Promise.all([
        api.get("/feasibility/page2"), api.get("/package-types/"), api.get("/assets/"),
        api.get("/warehouses/"),
      ]);
      const barred = {};
      page2.forEach((p) => p.barred_assets.forEach((a) => {
        (barred[a] = barred[a] || new Set()).add(p.package_type_id);
      }));
      setBarredByAsset(barred);
      setPackageTypes(pts);
      setAssets(as);
      setWarehouses(whs);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function toggleAvailable(a) {
    setBusy((b) => ({ ...b, [a.id]: true }));
    setError(null);
    try {
      await patch(`/assets/${a.id}`, { available: !a.available });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy((b) => ({ ...b, [a.id]: false }));
    }
  }

  const assetSort = (x, y) =>
    x.method.localeCompare(y.method) ||
    x.vehicle_type.localeCompare(y.vehicle_type) ||
    x.id.localeCompare(y.id, undefined, { numeric: true });
  const byLocation = [...warehouses]
    .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))
    .map((w) => ({ w, fleet: assets.filter((a) => a.home_warehouse_id === w.id).sort(assetSort) }))
    .filter((g) => g.fleet.length > 0);

  return (
    <div>
      <div className="page-header">
        <h1>What can move each package</h1>
        <details>
          <summary>How this page works</summary>
          <ul>
            <li>Vehicles grouped by base location, then method, then vehicle type — the transports, not the packages, are usually the limiting factor.</li>
            <li>Location headers show the fleet count per vehicle type; one row per vehicle below.</li>
            <li>Carrying ability (✓/✗ per package column) is per-vehicle, not per method — two ships of the same class can differ.</li>
            <li>Click a vehicle name to toggle it in or out of service for today; out-of-service vehicles leave the optimizer's model everywhere.</li>
          </ul>
        </details>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!barredByAsset && !error && <div className="loading-text">Loading…</div>}

      {barredByAsset && packageTypes && (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Vehicle</th>
                <th>Method</th>
                <th>Type</th>
                {packageTypes.map((pt) => (
                  <th key={pt.id}>{pt.name} <span className="muted" style={{ fontWeight: 400 }}>({pt.id})</span></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byLocation.map(({ w, fleet }) => (
                <FragmentRows key={w.id} w={w} fleet={fleet} packageTypes={packageTypes}
                              barredByAsset={barredByAsset} busy={busy} toggleAvailable={toggleAvailable} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
