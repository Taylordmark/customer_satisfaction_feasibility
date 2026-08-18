import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page5Schedule() {
  const [dailyCap, setDailyCap] = useState(5);
  const [policies, setPolicies] = useState([]);
  const [customerTypes, setCustomerTypes] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.get("/settings/"), api.get("/allocation-policies/"), api.get("/customer-types/")])
      .then(([settings, pol, types]) => {
        setDailyCap(settings.default_daily_cap);
        setPolicies(pol);
        setCustomerTypes(types);
        runSolve(settings.default_daily_cap);
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function typeName(id) {
    const t = customerTypes.find((t) => t.id === id);
    return t ? t.name : `type ${id}`;
  }

  async function runSolve(cap) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.post("/feasibility/page5", { daily_cap: cap });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const pctAchieved = result && result.score_possible > 0
    ? Math.round((result.score_achieved / result.score_possible) * 100)
    : 0;

  return (
    <div>
      <div className="page-header">
        <h1>5. How many deliveries fit in a day</h1>
        <p>Set how many delivery missions you can schedule today. This re-solves the full model — time budgets, refuel pairing, inventory, and any mission-allocation quotas — under that cap.</p>
      </div>

      <div className="panel">
        <div className="panel-title">Daily mission cap</div>
        <div className="slider-row" style={{ marginTop: 10 }}>
          <input
            type="range"
            min="0"
            max="20"
            value={dailyCap}
            onChange={(e) => setDailyCap(Number(e.target.value))}
          />
          <div className="slider-value">{dailyCap}</div>
        </div>
        <button className="btn btn-primary" onClick={() => runSolve(dailyCap)} disabled={loading}>
          {loading ? "Solving…" : "Run assessment"}
        </button>

        {policies.length > 0 && (
          <div style={{ marginTop: 14, fontSize: 13 }} className="muted">
            Active quotas: {policies.map((p) => `≥${Math.round(p.target_pct * 100)}% to ${typeName(p.customer_type_id)}`).join(" · ")}
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <>
          <div className="panel">
            <div style={{ display: "flex", gap: 32 }}>
              <div>
                <div className="muted" style={{ fontSize: 12 }}>Missions scheduled</div>
                <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 28, color: "var(--navy)" }}>
                  {result.deliveries_scheduled} <span className="muted" style={{ fontSize: 15, fontWeight: 400 }}>/ {result.daily_cap} cap</span>
                </div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 12 }}>Priority-weighted score</div>
                <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 28, color: pctAchieved === 100 ? "var(--good)" : "var(--navy)" }}>
                  {pctAchieved}% <span className="muted" style={{ fontSize: 15, fontWeight: 400 }}>({result.score_achieved} / {result.score_possible})</span>
                </div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 12 }}>Solver status</div>
                <div style={{ marginTop: 4 }}>
                  <span className={`badge ${result.status === "Optimal" ? "badge-good" : "badge-bad"}`}>{result.status}</span>
                </div>
              </div>
            </div>

            {Object.keys(result.mission_counts_by_type).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Missions by customer type</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {Object.entries(result.mission_counts_by_type).map(([name, count]) => (
                    <span key={name} className="badge badge-neutral">{name}: {count}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-title">Customer outcomes</div>
            <table>
              <thead>
                <tr><th>Customer</th><th>Type</th><th>Score</th><th>Result</th><th>Shortfall</th></tr>
              </thead>
              <tbody>
                {result.customers.map((c) => (
                  <tr key={c.customer_id}>
                    <td>{c.label}</td>
                    <td className="muted">{c.customer_type || "—"}</td>
                    <td>{c.score}</td>
                    <td>
                      <span className={`badge ${c.satisfied ? "badge-good" : "badge-bad"}`}>
                        {c.satisfied ? "satisfied" : "not satisfied"}
                      </span>
                    </td>
                    <td className="muted" style={{ fontSize: 12.5 }}>
                      {Object.keys(c.shortfall).length === 0 ? "—" :
                        Object.entries(c.shortfall).map(([k, s]) => `${k}: ${s.shipped}/${s.needed}`).join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <div className="panel-title">Dispatch plan</div>
            {result.dispatches.length === 0 ? (
              <div className="muted" style={{ fontSize: 13.5 }}>No missions scheduled at this cap.</div>
            ) : (
              <table>
                <thead>
                  <tr><th>Asset</th><th>From</th><th>Method</th><th>To</th><th>Refueler</th><th>Cargo</th></tr>
                </thead>
                <tbody>
                  {result.dispatches.map((d, i) => (
                    <tr key={i}>
                      <td>{d.asset_id}</td>
                      <td className="muted">{d.home_warehouse_id}</td>
                      <td>{d.method}</td>
                      <td>{d.customer_id}</td>
                      <td className="muted">{d.refueler_id || "—"}</td>
                      <td className="muted" style={{ fontSize: 12.5 }}>
                        {Object.entries(d.cargo).map(([k, q]) => `${q}×${k}`).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
