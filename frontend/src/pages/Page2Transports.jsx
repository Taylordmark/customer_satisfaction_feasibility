import { useEffect, useState } from "react";
import { api } from "../api";

export default function Page2Transports() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/feasibility/page2").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>2. What can move each package</h1>
        <p>Every package type against the transport methods able to carry it. A method's cargo restrictions apply to every asset that uses it, regardless of where that asset is based.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Package</th>
                <th>Eligible methods</th>
                <th>Barred methods</th>
                <th>Eligible assets</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.package_type_id}>
                  <td>{p.name} <span className="muted">({p.package_type_id})</span></td>
                  <td>
                    {p.eligible_methods.length === 0
                      ? <span className="badge badge-bad">none</span>
                      : p.eligible_methods.map((m) => <span key={m} className="badge badge-good" style={{ marginRight: 5 }}>{m}</span>)}
                  </td>
                  <td>
                    {p.barred_methods.length === 0
                      ? <span className="muted">—</span>
                      : p.barred_methods.map((m) => <span key={m} className="badge badge-bad" style={{ marginRight: 5 }}>{m}</span>)}
                  </td>
                  <td>{p.eligible_assets.length} asset{p.eligible_assets.length !== 1 ? "s" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
