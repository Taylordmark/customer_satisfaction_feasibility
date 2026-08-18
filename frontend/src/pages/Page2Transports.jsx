import { Fragment, useEffect, useState } from "react";
import { api } from "../api";

function FragmentRows({ w, fleet, packageTypes, barredByAsset }) {
  // Group into one row per (method, vehicle_type) — fleet is already sorted
  // by method then vehicle_type then id, so first-encounter order is stable.
  const typeGroups = [];
  const typeGroupIndex = new Map();
  fleet.forEach((a) => {
    const key = `${a.method}|${a.vehicle_type}`;
    let entry = typeGroupIndex.get(key);
    if (!entry) {
      entry = { method: a.method, vehicle_type: a.vehicle_type, vehicles: [] };
      typeGroupIndex.set(key, entry);
      typeGroups.push(entry);
    }
    entry.vehicles.push(a);
  });
  return (
    <Fragment>
      <tr>
        <td colSpan={3 + packageTypes.length}
            style={{ background: "var(--panel-alt, #f0f2f7)", fontWeight: 700, fontSize: 13 }}>
          {w.label} <span className="muted" style={{ fontWeight: 400 }}>({w.id})</span>
        </td>
      </tr>
      {typeGroups.map((g) => {
        const representative = g.vehicles[0];
        const barred = barredByAsset[representative.id] || new Set();
        const inServiceCount = g.vehicles.filter((a) => a.available).length;
        const total = g.vehicles.length;
        const ids = g.vehicles.map((a) => a.id).join(", ");
        return (
          <tr key={`${g.method}|${g.vehicle_type}`}>
            <td className="muted" style={{ fontSize: 12.5, paddingLeft: 18 }}>{g.method}</td>
            <td className="muted" style={{ fontSize: 12.5 }}>{g.vehicle_type}</td>
            <td title={`${ids} — toggle service on page 4`}>
              {inServiceCount < total
                ? <span className="muted">{inServiceCount} of {total} in service</span>
                : total}
            </td>
            {packageTypes.map((pt) => (
              <td key={pt.id} style={{ textAlign: "center" }}>
                {barred.has(pt.id)
                  ? <span style={{ color: "var(--bad, #b3261e)", fontWeight: 600 }} title={`${g.vehicle_type} cannot carry ${pt.name}`}>✗</span>
                  : <span style={{ color: "var(--good, #1b7f4d)", fontWeight: 600 }} title={`${g.vehicle_type} can carry ${pt.name}`}>✓</span>}
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
            <li>One row per vehicle type at each location, not per vehicle.</li>
            <li>Carrying ability (✓/✗ per package column) is determined by vehicle type alone — vehicles of the same type never meaningfully differ.</li>
            <li>The Count column shows fleet size for that type, and how many are currently in service if any are standing down. Hover the count for the individual vehicle IDs.</li>
            <li>To take a vehicle in or out of service, use the fleet-by-location panel on page 4.</li>
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
                <th>Method</th>
                <th>Type</th>
                <th>Count</th>
                {packageTypes.map((pt) => (
                  <th key={pt.id}>{pt.name} <span className="muted" style={{ fontWeight: 400 }}>({pt.id})</span></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byLocation.map(({ w, fleet }) => (
                <FragmentRows key={w.id} w={w} fleet={fleet} packageTypes={packageTypes}
                              barredByAsset={barredByAsset} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
