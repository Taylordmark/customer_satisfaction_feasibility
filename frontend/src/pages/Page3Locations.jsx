import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page3Locations() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/feasibility/page3").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>3. Where it can actually come from</h1>
        <p>Combines stock on hand with reachability. A warehouse counts as feasible for a package only if it has stock AND at least one asset there can carry that package type and reach the customer — directly, or with a refueler.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && data.map((c) => (
        <div className="panel" key={c.customer_id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
            <div className="panel-title">{c.label} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({c.customer_id})</span></div>
            <span className={`badge ${c.fully_feasible ? "badge-good" : "badge-bad"}`}>
              {c.fully_feasible ? "deliverable" : "not fully deliverable"}
            </span>
          </div>

          {c.packages.map((p) => (
            <div key={p.package_type_id} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 6 }}>
                <strong style={{ fontSize: 13.5 }}>{p.package_type_id}</strong>
                <span className="muted" style={{ fontSize: 12.5 }}>needed: {p.qty_needed}</span>
                <span className={`badge ${p.any_feasible ? "badge-good" : "badge-bad"}`} style={{ marginLeft: "auto" }}>
                  {p.any_feasible ? "feasible" : "no feasible source"}
                </span>
              </div>
              {p.warehouses.length === 0 ? (
                <div className="muted" style={{ fontSize: 13 }}>No warehouse has stock or a capable asset for this package.</div>
              ) : (
                <table>
                  <thead>
                    <tr><th>Warehouse</th><th>Stock</th><th>Capable assets</th><th></th></tr>
                  </thead>
                  <tbody>
                    {p.warehouses.map((w) => (
                      <tr key={w.warehouse_id}>
                        <td>{w.label} <span className="muted">({w.warehouse_id})</span></td>
                        <td>{w.stock}</td>
                        <td>
                          {w.capable_assets.length === 0 ? <span className="muted">none</span> : w.capable_assets.map((a) => (
                            <span key={a.asset_id} className="badge badge-neutral" style={{ marginRight: 5 }}>
                              {a.asset_id}{!a.direct ? ` (via ${a.via_refuelers.join(", ")})` : ""}
                            </span>
                          ))}
                        </td>
                        <td>
                          <span className={`badge ${w.feasible ? "badge-good" : "badge-bad"}`}>
                            {w.feasible ? "yes" : "no"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
