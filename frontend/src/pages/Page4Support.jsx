import { useEffect, useState } from "react";
import { api } from "../api";
import { patch } from "../patch";

function SupportBadge({ c }) {
  if (c.unreachable) return <span className="badge badge-bad">unreachable</span>;
  if (c.needs_support) return <span className="badge badge-warn">refueler required</span>;
  return <span className="badge badge-good">deliverable without support</span>;
}

function outOfServiceStyle(available) {
  const off = available === false;
  return {
    opacity: off ? 0.5 : 1,
    textDecoration: off ? "line-through" : "none",
  };
}

export default function Page4Support() {
  const [data, setData] = useState(null);
  const [assetsById, setAssetsById] = useState({});
  const [refuelersById, setRefuelersById] = useState({});
  const [pins, setPins] = useState([]);
  const [error, setError] = useState(null);
  const [busyAssets, setBusyAssets] = useState({}); // asset_id -> bool
  const [busyRefuelers, setBusyRefuelers] = useState({}); // refueler_id -> bool
  const [busyTankerPins, setBusyTankerPins] = useState({}); // `${customerId}|${assetId}|${refuelerId}` -> bool

  async function load() {
    try {
      const [d, assets, refuelers, pm] = await Promise.all([
        api.get("/feasibility/page4"), api.get("/assets/"), api.get("/refuelers/"), api.get("/planned-missions/"),
      ]);
      setData(d);
      setAssetsById(Object.fromEntries(assets.map((a) => [a.id, a])));
      setRefuelersById(Object.fromEntries(refuelers.map((f) => [f.id, f])));
      setPins(pm);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function toggleAsset(id) {
    const a = assetsById[id];
    setBusyAssets((b) => ({ ...b, [id]: true }));
    setError(null);
    try {
      await patch(`/assets/${id}`, { available: !a.available });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyAssets((b) => ({ ...b, [id]: false }));
    }
  }

  async function toggleRefueler(id) {
    const f = refuelersById[id];
    setBusyRefuelers((b) => ({ ...b, [id]: true }));
    setError(null);
    try {
      await patch(`/refuelers/${id}`, { available: !f.available });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyRefuelers((b) => ({ ...b, [id]: false }));
    }
  }

  function tankerPin(customerId, assetId, refuelerId) {
    return pins.find((p) => p.customer_id === customerId && p.asset_id === assetId && p.refueler_id === refuelerId);
  }

  async function toggleTankerPin(customerId, assetId, refuelerId) {
    const key = `${customerId}|${assetId}|${refuelerId}`;
    setBusyTankerPins((b) => ({ ...b, [key]: true }));
    setError(null);
    try {
      const existing = tankerPin(customerId, assetId, refuelerId);
      if (existing) await api.del(`/planned-missions/${existing.id}`);
      else await api.post("/planned-missions/", { customer_id: customerId, asset_id: assetId, refueler_id: refuelerId });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyTankerPins((b) => ({ ...b, [key]: false }));
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>4. What support does delivery need</h1>
        <p>For each customer: which capable vehicles reach them on their own fuel, and which only get there with a refueler — and which tankers can provide that support. Out-of-service vehicles and refuelers are shown grayed out rather than hidden. Click a tanker to pin that exact pairing as a manual mission. The controlling team is shown per vehicle, since tasking authority follows from the location/vehicle combination.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="loading-text">Loading…</div>}

      {data && data.per_customer.map((c) => (
        <div className="panel" key={c.customer_id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
            <div className="panel-title">{c.label} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>({c.customer_id})</span></div>
            <SupportBadge c={c} />
          </div>

          {c.direct_assets.length === 0 && c.supported_assets.length === 0 ? (
            <div className="muted" style={{ fontSize: 13.5 }}>No capable vehicle can reach this customer, even with refueler support.</div>
          ) : (
            <table>
              <thead>
                <tr><th>Vehicle</th><th>Type</th><th>Based at</th><th>Can carry</th><th>Controlled by</th><th>Support needed</th></tr>
              </thead>
              <tbody>
                {c.direct_assets.map((a) => (
                  <tr key={a.asset_id} style={outOfServiceStyle(a.available)}>
                    <td>{a.asset_id}{a.available === false ? <span className="muted" style={{ marginLeft: 6, fontSize: 11.5 }}>(out of service)</span> : null}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.vehicle_type}</td>
                    <td className="muted">{a.warehouse_id}</td>
                    <td>{a.carries.map((k) => <span key={k} className="badge badge-neutral" style={{ marginRight: 4 }}>{k}</span>)}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.team}</td>
                    <td><span className="muted">none — reaches unaided</span></td>
                  </tr>
                ))}
                {c.supported_assets.map((a) => (
                  <tr key={a.asset_id} style={outOfServiceStyle(a.available)}>
                    <td>{a.asset_id}{a.available === false ? <span className="muted" style={{ marginLeft: 6, fontSize: 11.5 }}>(out of service)</span> : null}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.vehicle_type}</td>
                    <td className="muted">{a.warehouse_id}</td>
                    <td>{a.carries.map((k) => <span key={k} className="badge badge-neutral" style={{ marginRight: 4 }}>{k}</span>)}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{a.team}</td>
                    <td>
                      {a.refuelers.map((f) => {
                        const pinned = !!tankerPin(c.customer_id, a.asset_id, f.refueler_id);
                        const key = `${c.customer_id}|${a.asset_id}|${f.refueler_id}`;
                        const refuelerOff = f.available === false;
                        return (
                          <button
                            type="button"
                            key={f.refueler_id}
                            className={`badge btn-unstyled ${pinned ? "badge-good" : "badge-warn"}`}
                            onClick={() => toggleTankerPin(c.customer_id, a.asset_id, f.refueler_id)}
                            disabled={!!busyTankerPins[key]}
                            aria-pressed={pinned}
                            aria-label={pinned
                              ? `Pinned: ${a.asset_id} to ${c.label} with ${f.refueler_id}. Activate to unpin.`
                              : `Pin ${a.asset_id} to ${c.label} with ${f.refueler_id}, based at ${f.warehouse_id}, controlled by ${f.team}.`}
                            title={pinned
                              ? `Pinned: ${a.asset_id} → ${c.label} with ${f.refueler_id}. Click to unpin.`
                              : `${f.refueler_id} is based at ${f.warehouse_id}, controlled by ${f.team}. Click to pin this pairing as a manual mission.`}
                            style={{
                              marginRight: 5,
                              opacity: refuelerOff ? 0.5 : 1,
                              textDecoration: refuelerOff ? "line-through" : "none",
                            }}
                          >
                            {pinned ? "📌 " : ""}{f.refueler_id} ({f.warehouse_id}){refuelerOff ? " — out of service" : ""}
                          </button>
                        );
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}

      {data && (
        <div className="panel">
          <div className="panel-title">Fleet by location</div>
          <div className="panel-subtitle">What's stationed where, with a count per vehicle type, and who controls it. Click any vehicle or refueler to toggle it in or out of service for today.</div>
          <table>
            <thead>
              <tr><th>Location</th><th>Count by type</th><th>Vehicles</th><th>Refuelers</th></tr>
            </thead>
            <tbody>
              {data.by_location.map((w) => (
                <tr key={w.warehouse_id}>
                  <td>{w.label} <span className="muted">({w.warehouse_id})</span></td>
                  <td style={{ fontSize: 12.5 }}>
                    {Object.entries(w.type_counts).map(([t, n]) => (
                      <span key={t} className="badge badge-neutral" style={{ marginRight: 4, marginBottom: 3 }}>{n}× {t}</span>
                    ))}
                    {Object.keys(w.type_counts).length === 0 && <span className="muted">—</span>}
                  </td>
                  <td>
                    {w.assets.map((a) => (
                      <button
                        type="button"
                        key={a.asset_id}
                        className="badge badge-neutral btn-unstyled"
                        onClick={() => toggleAsset(a.asset_id)}
                        disabled={!!busyAssets[a.asset_id]}
                        aria-pressed={a.available}
                        aria-label={`${a.asset_id}, ${a.vehicle_type}, controlled by ${a.team} — ${a.available ? "in service, click to stand down" : "out of service, click to return to service"}`}
                        title={`${a.vehicle_type} — controlled by ${a.team}. ${a.available ? "In service — click to stand down." : "Out of service — click to return to service."}`}
                        style={{ marginRight: 4, marginBottom: 3,
                                 textDecoration: a.available ? "none" : "line-through",
                                 opacity: a.available ? 1 : 0.5 }}
                      >{a.asset_id}</button>
                    ))}
                  </td>
                  <td>
                    {w.refuelers.length === 0 ? <span className="muted">—</span> : w.refuelers.map((f) => (
                      <button
                        type="button"
                        key={f.refueler_id}
                        className="badge badge-neutral btn-unstyled"
                        onClick={() => toggleRefueler(f.refueler_id)}
                        disabled={!!busyRefuelers[f.refueler_id]}
                        aria-pressed={f.available}
                        aria-label={`${f.refueler_id}, ${f.vehicle_type}, controlled by ${f.team} — ${f.available ? "in service, click to stand down" : "out of service, click to return to service"}`}
                        title={`${f.vehicle_type} — controlled by ${f.team}. ${f.available ? "In service — click to stand down." : "Out of service — click to return to service."}`}
                        style={{ marginRight: 4,
                                 textDecoration: f.available ? "none" : "line-through",
                                 opacity: f.available ? 1 : 0.5 }}
                      >{f.refueler_id}</button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
