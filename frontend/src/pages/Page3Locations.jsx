import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page3Locations() {
  const [data, setData] = useState(null);
  const [pins, setPins] = useState([]);
  const [error, setError] = useState(null);
  const [busyPins, setBusyPins] = useState({}); // `${customerId}|${warehouseId}` -> bool

  async function load() {
    try {
      const [d, pm] = await Promise.all([api.get("/feasibility/page3"), api.get("/planned-missions/")]);
      setData(d);
      setPins(pm);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  function sourcePin(customerId, warehouseId) {
    return pins.find((p) => p.customer_id === customerId && p.source_warehouse_id === warehouseId && !p.asset_id);
  }

  async function toggleSourcePin(customerId, warehouseId) {
    const key = `${customerId}|${warehouseId}`;
    setBusyPins((b) => ({ ...b, [key]: true }));
    setError(null);
    try {
      const existing = sourcePin(customerId, warehouseId);
      if (existing) await api.del(`/planned-missions/${existing.id}`);
      else await api.post("/planned-missions/", { customer_id: customerId, source_warehouse_id: warehouseId });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyPins((b) => ({ ...b, [key]: false }));
    }
  }

  // Defensive fallback for when the backend hasn't landed p.partial yet: derive
  // "partial" from any warehouse row that itself reports partial.
  function packagePartial(p) {
    if (p.partial !== undefined) return p.partial;
    return !p.any_feasible && (p.warehouses || []).some((w) => w.partial);
  }

  return (
    <div>
      <div className="page-header">
        <h1>What locations have the packages and transport to satisfy</h1>
        <details>
          <summary>How this page works</summary>
          <ul>
            <li>Combines stock on hand with reachability, per warehouse.</li>
            <li><strong>Feasible</strong> = full stock for the quantity needed AND an in-service asset there that carries it and reaches the customer, directly or via refueler.</li>
            <li><strong>Partial</strong> = some stock but not enough — the solver may still use it, split across sources.</li>
            <li>A customer is deliverable if any one bundle option has a feasible source.</li>
            <li>Out-of-service vehicles show grayed out, not hidden. Click <strong>pin source</strong> to lock a customer's delivery to one warehouse.</li>
          </ul>
        </details>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && data.map((c) => (
        <div className="panel" key={c.customer_id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
            <div className="panel-title">{c.label} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({c.customer_id})</span></div>
            <span className={`badge ${c.fully_feasible ? "badge-good" : "badge-bad"}`}>
              {c.fully_feasible ? "deliverable" : "not deliverable"}
            </span>
          </div>

          {c.packages.map((p) => {
            const partial = packagePartial(p);
            return (
            <div key={p.package_type_id} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 6 }}>
                <strong style={{ fontSize: 13.5 }}>{p.package_type_id}</strong>
                <span className="muted" style={{ fontSize: 12.5 }}>needed: {p.qty_needed}</span>
                <span
                  className={`badge ${p.any_feasible ? "badge-good" : partial ? "badge-warn" : "badge-bad"}`}
                  style={{ marginLeft: "auto" }}
                >
                  {p.any_feasible ? "feasible" : partial ? "partial — solver may split across sources" : "no feasible source"}
                </span>
              </div>
              {p.warehouses.length === 0 ? (
                <div className="muted" style={{ fontSize: 13 }}>No warehouse has stock or a capable asset for this package.</div>
              ) : (
                <table>
                  <thead>
                    <tr><th>Warehouse</th><th>Stock</th><th>Capable assets</th><th></th><th>Source</th></tr>
                  </thead>
                  <tbody>
                    {p.warehouses.map((w) => {
                      const pinned = !!sourcePin(c.customer_id, w.warehouse_id);
                      const pinKey = `${c.customer_id}|${w.warehouse_id}`;
                      return (
                        <tr key={w.warehouse_id}>
                          <td>{w.label} <span className="muted">({w.warehouse_id})</span></td>
                          <td>{w.stock}</td>
                          <td>
                            {w.capable_assets.length === 0 ? <span className="muted">none</span> : w.capable_assets.map((a) => {
                              const outOfService = a.available === false;
                              return (
                                <span
                                  key={a.asset_id}
                                  className="badge badge-neutral"
                                  style={{
                                    marginRight: 5,
                                    opacity: outOfService ? 0.5 : 1,
                                    textDecoration: outOfService ? "line-through" : "none",
                                  }}
                                  title={outOfService ? `${a.asset_id} is out of service` : undefined}
                                >
                                  {a.asset_id}{!a.direct ? ` (via ${a.via_refuelers.join(", ")})` : ""}
                                  {outOfService ? " — out of service" : ""}
                                </span>
                              );
                            })}
                          </td>
                          <td>
                            <span className={`badge ${w.feasible ? "badge-good" : w.partial ? "badge-warn" : "badge-bad"}`}>
                              {w.feasible ? "yes" : w.partial ? "partial" : "no"}
                            </span>
                          </td>
                          <td>
                            {(w.feasible || w.partial || pinned) && (
                              <button
                                className="btn btn-sm btn-ghost"
                                onClick={() => toggleSourcePin(c.customer_id, w.warehouse_id)}
                                disabled={!!busyPins[pinKey]}
                                aria-pressed={pinned}
                              >
                                {pinned ? "✓ pinned — unpin" : "pin source"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
