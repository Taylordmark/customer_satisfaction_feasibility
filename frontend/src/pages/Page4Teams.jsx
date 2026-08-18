import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page4Teams() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/feasibility/page4").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>4. Who controls the vehicles</h1>
        <p>Every transport control team, what it owns, and — for each customer — which teams you'd actually need to coordinate with or task to make delivery possible.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && (
        <>
          <div className="panel">
            <div className="panel-title">Org chart</div>
            <div className="panel-subtitle">Ownership is tasking authority — each asset and refueler is controlled by exactly one team.</div>
            <table>
              <thead>
                <tr><th>Team</th><th>Stationed at</th><th>Assets</th><th>Refuelers</th></tr>
              </thead>
              <tbody>
                {data.org_chart.map((t) => (
                  <tr key={t.team_id}>
                    <td>{t.name}</td>
                    <td className="muted">{t.warehouse_id || "—"}</td>
                    <td>{t.assets.length ? t.assets.join(", ") : <span className="muted">none</span>}</td>
                    <td>{t.refuelers.length ? t.refuelers.join(", ") : <span className="muted">none</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.unowned_assets.length > 0 && (
              <div className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
                Unassigned assets (no owning team): {data.unowned_assets.join(", ")}
              </div>
            )}
          </div>

          {data.per_customer.map((c) => (
            <div className="panel" key={c.customer_id}>
              <div className="panel-title">{c.label} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({c.customer_id})</span></div>
              {c.teams_to_coordinate.length === 0 ? (
                <div className="muted" style={{ fontSize: 13.5, marginTop: 6 }}>No team currently has a capable, in-range asset for this customer.</div>
              ) : (
                <table style={{ marginTop: 8 }}>
                  <thead>
                    <tr><th>Team to coordinate with</th><th>Their assets that could do it</th></tr>
                  </thead>
                  <tbody>
                    {c.teams_to_coordinate.map((t) => (
                      <tr key={t.team_id ?? "unassigned"}>
                        <td>{t.team_name}</td>
                        <td>{t.assets.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
