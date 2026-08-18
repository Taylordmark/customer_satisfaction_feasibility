import { useEffect, useState } from "react";
import { api } from "../api";
import { patch } from "../patch";

export default function Page2Transports() {
  const [barredByAsset, setBarredByAsset] = useState(null); // {asset_id: Set(package ids)}
  const [packageTypes, setPackageTypes] = useState(null);
  const [assets, setAssets] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState({}); // asset_id -> bool

  async function load() {
    try {
      const [page2, pts, as] = await Promise.all([
        api.get("/feasibility/page2"), api.get("/package-types/"), api.get("/assets/"),
      ]);
      const barred = {};
      page2.forEach((p) => p.barred_assets.forEach((a) => {
        (barred[a] = barred[a] || new Set()).add(p.package_type_id);
      }));
      setBarredByAsset(barred);
      setPackageTypes(pts);
      setAssets(as);
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

  const sorted = [...assets].sort((x, y) =>
    x.method === y.method ? x.id.localeCompare(y.id, undefined, { numeric: true }) : x.method.localeCompare(y.method));

  return (
    <div>
      <div className="page-header">
        <h1>2. What can move each package</h1>
        <p>One row per vehicle, one column per package type — carrying ability is per-vehicle, not per method, so two ships can differ. Click a row's vehicle name to toggle it in or out of service for today; out-of-service vehicles leave the optimizer's model everywhere.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!barredByAsset && !error && <div className="loading-text">Loading…</div>}

      {barredByAsset && packageTypes && (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Vehicle</th>
                <th>Type</th>
                <th>Method</th>
                <th>Base</th>
                {packageTypes.map((pt) => (
                  <th key={pt.id}>{pt.name} <span className="muted" style={{ fontWeight: 400 }}>({pt.id})</span></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => {
                const barred = barredByAsset[a.id] || new Set();
                const isBusy = !!busy[a.id];
                return (
                  <tr key={a.id} style={a.available ? {} : { opacity: 0.45 }}>
                    <td>
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
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.vehicle_type}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.method}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.home_warehouse_id}</td>
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
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
