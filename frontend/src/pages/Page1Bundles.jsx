import { useEffect, useState } from "react";
import { api } from "../api";
import { patch } from "../patch";

export default function Page1Bundles() {
  const [data, setData] = useState(null);
  const [packageTypes, setPackageTypes] = useState(null);
  const [customersById, setCustomersById] = useState({});
  const [pins, setPins] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState({}); // key -> bool, keys: `inc-<id>` / `star-<id>`

  async function load() {
    try {
      const [d, pts, custs, pm] = await Promise.all([
        api.get("/feasibility/page1"),
        api.get("/package-types/"),
        api.get("/customers/"),
        api.get("/planned-missions/"),
      ]);
      setData(d);
      setPackageTypes(pts);
      setCustomersById(Object.fromEntries(custs.map((c) => [c.id, c])));
      setPins(pm);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function withBusy(key, fn) {
    setBusy((b) => ({ ...b, [key]: true }));
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy((b) => ({ ...b, [key]: false }));
    }
  }

  async function toggleIncluded(id) {
    const cust = customersById[id];
    await withBusy(`inc-${id}`, async () => {
      await patch(`/customers/${id}`, { included: !cust.included });
      await load();
    });
  }

  // a "must satisfy" star is a customer-only planned mission
  function starPin(id) {
    return pins.find((p) => p.customer_id === id && !p.asset_id && !p.refueler_id && !p.package_type_id && !p.source_warehouse_id);
  }

  async function toggleStar(id) {
    const existing = starPin(id);
    await withBusy(`star-${id}`, async () => {
      if (existing) await api.del(`/planned-missions/${existing.id}`);
      else await api.post("/planned-missions/", { customer_id: id });
      await load();
    });
  }

  return (
    <div>
      <div className="page-header">
        <h1>What satisfies each customer</h1>
        <details>
          <summary>How this page works</summary>
          <ul>
            <li>One row per customer (ranked by priority, 1 = highest), one column per package type.</li>
            <li>Each cell is the quantity needed — columns are <strong>alternatives</strong>, so fully delivering any one option satisfies the customer.</li>
            <li>Uncheck <strong>In plan</strong> to exclude a customer from today's problem.</li>
            <li>Click <strong>★</strong> to pin a customer as must-satisfy.</li>
          </ul>
        </details>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {(!data || !packageTypes) && !error && <div className="loading-text">Loading…</div>}

      {data && packageTypes && (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>In plan</th>
                <th>★</th>
                <th>Rank</th>
                <th>Customer</th>
                <th>Type</th>
                {packageTypes.map((pt) => (
                  <th key={pt.id}>{pt.name} <span className="muted" style={{ fontWeight: 400 }}>({pt.id})</span></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((c) => {
                const qtyByPackage = Object.fromEntries(c.items.map((it) => [it.package_type_id, it.qty_needed]));
                const cust = customersById[c.customer_id];
                const included = cust ? cust.included : true;
                const starred = !!starPin(c.customer_id);
                const incBusy = !!busy[`inc-${c.customer_id}`];
                const starBusy = !!busy[`star-${c.customer_id}`];
                return (
                  <tr key={c.customer_id} style={included ? {} : { opacity: 0.45 }}>
                    <td>
                      <input
                        type="checkbox" checked={included} disabled={incBusy}
                        onChange={() => toggleIncluded(c.customer_id)}
                        title="Include in today's plan"
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-unstyled"
                        onClick={() => toggleStar(c.customer_id)}
                        disabled={!included || starBusy}
                        aria-pressed={starred}
                        aria-label={starred ? `Un-pin ${c.label} as must-satisfy` : `Pin ${c.label} as must-satisfy today`}
                        title={starred ? "Un-pin must-satisfy" : "Pin as must-satisfy today"}
                        style={{ padding: 0, margin: 0, fontSize: 16, color: starred ? "#c9a227" : "#c8cbe0" }}
                      >★</button>
                    </td>
                    <td><span className="badge badge-neutral">#{c.rank}</span></td>
                    <td>{c.label} <span className="muted">({c.customer_id})</span></td>
                    <td className="muted">{c.customer_type || "—"}</td>
                    {packageTypes.map((pt) => (
                      <td key={pt.id}>
                        {qtyByPackage[pt.id] !== undefined
                          ? <span className="badge badge-good">{qtyByPackage[pt.id]}</span>
                          : <span className="muted">—</span>}
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
