import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page1Bundles() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/feasibility/page1").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>1. What satisfies each customer</h1>
        <p>The exact package types and quantities a customer needs. A customer isn't counted as satisfied until every line below arrives — partial delivery doesn't count.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && data.map((c) => (
        <div className="panel" key={c.customer_id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div className="panel-title">{c.label} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({c.customer_id})</span></div>
            <div style={{ display: "flex", gap: 8 }}>
              {c.customer_type && <span className="badge badge-neutral">{c.customer_type}</span>}
              <span className="badge badge-neutral">score {c.score}</span>
            </div>
          </div>
          {c.items.length === 0 ? (
            <div className="muted" style={{ fontSize: 13.5, marginTop: 8 }}>No bundle defined for this customer.</div>
          ) : (
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr><th>Package</th><th>Type ID</th><th>Qty needed</th></tr>
              </thead>
              <tbody>
                {c.items.map((it) => (
                  <tr key={it.package_type_id}>
                    <td>{it.name}</td>
                    <td className="muted">{it.package_type_id}</td>
                    <td>{it.qty_needed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}
