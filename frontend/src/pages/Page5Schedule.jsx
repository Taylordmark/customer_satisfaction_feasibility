import { useEffect, useState } from "react";
import { api } from "../api";

const EMPTY_DRAFT = { customer_id: "", asset_id: "", refueler_id: "", package_type_id: "", source_warehouse_id: "" };

function clampPct(raw) {
  if (raw === "") return "";
  const n = Number(raw);
  if (Number.isNaN(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

export default function Page5Schedule() {
  const [cap, setCap] = useState(null);
  const [defaultDailyCap, setDefaultDailyCap] = useState(0);
  const [customerTypes, setCustomerTypes] = useState([]);
  const [quotaPct, setQuotaPct] = useState({}); // {customer_type_id: percent 0-100}
  const [customers, setCustomers] = useState([]);
  const [assets, setAssets] = useState([]);
  const [refuelers, setRefuelers] = useState([]);
  const [packageTypes, setPackageTypes] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [pins, setPins] = useState([]);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [result, setResult] = useState(null);
  const [lastRunInputs, setLastRunInputs] = useState(null); // { cap, quotasKey, pinsKey } used to produce `result`
  const [selectedMode, setSelectedMode] = useState("rank_weighted");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [busyPins, setBusyPins] = useState({}); // pin id -> bool
  const [warningsDismissed, setWarningsDismissed] = useState(false);

  const MAX_CAP = Math.max(30, customers.length, defaultDailyCap || 0);

  async function loadPins() {
    setPins(await api.get("/planned-missions/"));
  }

  useEffect(() => {
    Promise.all([
      api.get("/settings/"), api.get("/customer-types/"), api.get("/allocation-policies/"),
      api.get("/customers/"), api.get("/assets/"), api.get("/refuelers/"),
      api.get("/package-types/"), api.get("/warehouses/"), api.get("/planned-missions/"),
    ])
      .then(([settings, types, policies, custs, as, rf, pts, whs, pm]) => {
        setCap(settings.default_daily_cap);
        setDefaultDailyCap(settings.default_daily_cap || 0);
        setCustomerTypes(types);
        setCustomers(custs);
        setAssets(as);
        setRefuelers(rf);
        setPackageTypes(pts);
        setWarehouses(whs);
        setPins(pm);
        const pct = {};
        policies.forEach((p) => { pct[p.customer_type_id] = Math.round(p.target_pct * 100); });
        setQuotaPct(pct);
      })
      .catch((e) => setError(e.message));
  }, []);

  function quotasFromPct(pctMap) {
    return customerTypes
      .filter((t) => Number(pctMap[t.id]) > 0)
      .map((t) => ({ customer_type_id: t.id, target_pct: Number(pctMap[t.id]) / 100 }));
  }

  function quotasKey(quotas) {
    return quotas.map((q) => `${q.customer_type_id}:${q.target_pct}`).sort().join(",");
  }

  function pinsKey(pinList) {
    return pinList.map((p) => p.id).slice().sort().join(",");
  }

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const quotas = quotasFromPct(quotaPct);
      const res = await api.post("/feasibility/page5", { daily_cap: cap, quotas });
      setResult(res);
      setWarningsDismissed(false);
      setLastRunInputs({ cap, quotasKey: quotasKey(quotas), pinsKey: pinsKey(pins) });
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (cap !== null && !result && !running) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cap]);

  const floorsSum = customerTypes.reduce((sum, t) => sum + (Number(quotaPct[t.id]) || 0), 0);

  const currentQuotasKey = quotasKey(quotasFromPct(quotaPct));
  const currentPinsKey = pinsKey(pins);
  const isStale = !!(result && lastRunInputs && (
    lastRunInputs.cap !== cap ||
    lastRunInputs.quotasKey !== currentQuotasKey ||
    lastRunInputs.pinsKey !== currentPinsKey
  ));

  async function addPin() {
    if (!draft.customer_id) return;
    const payload = Object.fromEntries(Object.entries(draft).map(([k, v]) => [k, v || null]));
    try {
      await api.post("/planned-missions/", payload);
      setDraft(EMPTY_DRAFT);
      await loadPins();
    } catch (e) {
      setError(e.message);
    }
  }

  async function removePin(id) {
    setBusyPins((b) => ({ ...b, [id]: true }));
    setError(null);
    try {
      await api.del(`/planned-missions/${id}`);
      await loadPins();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyPins((b) => ({ ...b, [id]: false }));
    }
  }

  function pinDescription(p) {
    const cust = customers.find((c) => c.id === p.customer_id);
    const parts = [cust ? cust.label : p.customer_id];
    if (p.asset_id) parts.push(`via ${p.asset_id}`);
    if (p.refueler_id) parts.push(`with ${p.refueler_id}`);
    if (p.package_type_id) parts.push(`delivering ${p.package_type_id}`);
    if (p.source_warehouse_id) parts.push(`from ${p.source_warehouse_id}`);
    return parts.join(" ");
  }

  const selected = result?.modes?.find((m) => m.mode === selectedMode) ?? result?.modes?.[0];
  const anyFloorActive = (result?.quotas_applied?.length || 0) > 0;

  return (
    <div>
      <div className="page-header">
        <h1>5. How many deliveries fit in a day</h1>
        <p>Pin any missions you've already decided on, set the daily cap and per-type mission share floors, then run. Pins are hard constraints that count against the cap and quotas; the optimizer fills the remaining freedom, solved once per objective so you can compare and choose.</p>
      </div>

      <div className="panel">
        <div className="panel-title">Manual missions</div>
        <div className="panel-subtitle">Only Customer is required — anything left blank stays the optimizer's choice. Conflicting pins make the run refuse and explain rather than being silently dropped.</div>
        {pins.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            {pins.map((p) => (
              <span key={p.id} className="badge badge-neutral" style={{ marginRight: 6, marginBottom: 4 }}>
                📌 {pinDescription(p)}
                <button
                  type="button"
                  className="btn-unstyled"
                  onClick={() => removePin(p.id)}
                  disabled={!!busyPins[p.id]}
                  aria-label={`Remove pin: ${pinDescription(p)}`}
                  title="Remove pin"
                  style={{ padding: 0, margin: 0, marginLeft: 6, fontWeight: 700 }}
                >×</button>
              </span>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <select className="table-input" value={draft.customer_id} onChange={(e) => setDraft({ ...draft, customer_id: e.target.value })}>
            <option value="">— customer —</option>
            {customers.filter((c) => c.included).map((c) => <option key={c.id} value={c.id}>#{c.priority_rank} {c.label}</option>)}
          </select>
          <select className="table-input" value={draft.asset_id} onChange={(e) => setDraft({ ...draft, asset_id: e.target.value })}>
            <option value="">— any asset —</option>
            {assets.filter((a) => a.available).map((a) => <option key={a.id} value={a.id}>{a.id} ({a.vehicle_type})</option>)}
          </select>
          <select className="table-input" value={draft.refueler_id} onChange={(e) => setDraft({ ...draft, refueler_id: e.target.value })}>
            <option value="">— any refueler —</option>
            {refuelers.filter((f) => f.available).map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
          </select>
          <select className="table-input" value={draft.package_type_id} onChange={(e) => setDraft({ ...draft, package_type_id: e.target.value })}>
            <option value="">— any option —</option>
            {packageTypes.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <select className="table-input" value={draft.source_warehouse_id} onChange={(e) => setDraft({ ...draft, source_warehouse_id: e.target.value })}>
            <option value="">— any source —</option>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
          </select>
          <button className="btn btn-primary btn-sm" onClick={addPin} disabled={!draft.customer_id}>+ Pin mission</button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">Daily mission cap</div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 8 }}>
          <input
            type="range" min="1" max={MAX_CAP} value={cap ?? 1}
            onChange={(e) => setCap(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <strong style={{ fontSize: 22, minWidth: 34, textAlign: "right" }}>{cap ?? "…"}</strong>
        </div>

        <div className="panel-title" style={{ marginTop: 18 }}>Mission share floors by customer type</div>
        <div className="panel-subtitle">Minimum % of the day's missions (manual ones included) that must go to each type. Leave 0 for no floor. An impossible floor forces an empty schedule rather than being ignored.</div>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          {customerTypes.map((t) => (
            <label key={t.id} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13.5 }}>
              {t.name}
              <input
                className="table-input" type="number" min="0" max="100" style={{ width: 64 }}
                value={quotaPct[t.id] ?? 0}
                onChange={(e) => setQuotaPct({ ...quotaPct, [t.id]: clampPct(e.target.value) })}
              />%
            </label>
          ))}
        </div>
        {floorsSum > 100 && (
          <div className="inline-warning" role="alert">
            floors sum to {floorsSum}% — guarantees an empty schedule, since each mission counts toward exactly one type
          </div>
        )}

        <div style={{ marginTop: 16 }}>
          <button className="btn btn-primary" onClick={run} disabled={running || cap === null}>
            {running ? "Solving…" : "Run assessment"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && result.data_warnings?.length > 0 && !warningsDismissed && (
        <div className="warning-banner" role="alert">
          <div style={{ flex: 1 }}>
            <strong style={{ display: "block", marginBottom: 4 }}>Data warnings</strong>
            {result.data_warnings.map((w, i) => <div key={i}>{w}</div>)}
          </div>
          <button
            type="button"
            className="btn-unstyled"
            onClick={() => setWarningsDismissed(true)}
            aria-label="Dismiss data warnings"
            style={{ padding: 0, margin: 0, fontWeight: 700 }}
          >×</button>
        </div>
      )}

      {result && result.pin_conflicts?.length > 0 && (
        <div className="panel" style={{ borderColor: "var(--bad, #b3261e)" }}>
          <div className="panel-title">Can't run — your pinned missions conflict</div>
          <div className="panel-subtitle">Human decisions are never silently overridden. Fix or remove these pins, then run again.</div>
          <ul style={{ fontSize: 13.5, paddingLeft: 20 }}>
            {result.pin_conflicts.map((c, i) => <li key={i} style={{ marginBottom: 4 }}>{c}</li>)}
          </ul>
        </div>
      )}

      {result && result.modes?.length > 0 && (
        <>
          <div className="panel-subtitle" style={{ marginBottom: 4 }}>
            This run used: daily cap <strong>{result.daily_cap}</strong>
            {result.quotas_applied?.length > 0 && (
              <> · floors {result.quotas_applied.map((q) => `${q.name || q.customer_type_id} ≥${Math.round(q.target_pct * 100)}%`).join(", ")}</>
            )}
          </div>

          {isStale && (
            <div className="stale-banner" role="status">
              Inputs changed since this run — re-run to update.
            </div>
          )}

          <div className={isStale ? "results-dim" : ""}>
            {(result.excluded_customers?.length > 0 || result.out_of_service?.length > 0) && (
              <div className="panel-subtitle" style={{ marginBottom: 10 }}>
                {result.excluded_customers?.length > 0 && <>Excluded today: {result.excluded_customers.join(", ")}. </>}
                {result.out_of_service?.length > 0 && <>Out of service: {result.out_of_service.join(", ")}.</>}
              </div>
            )}
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              {result.modes.map((m) => {
                const emptyDueToFloors = m.status === "Optimal" && m.deliveries_scheduled === 0 && anyFloorActive;
                return (
                  <button
                    type="button"
                    key={m.mode}
                    className="panel card-btn-reset"
                    onClick={() => setSelectedMode(m.mode)}
                    aria-pressed={selected?.mode === m.mode}
                    aria-label={`${m.label} — select this mode`}
                    style={{
                      flex: "1 1 200px", cursor: "pointer", marginBottom: 18,
                      outline: selected?.mode === m.mode ? "2px solid var(--navy)" : "none",
                    }}
                  >
                    <div className="panel-title" style={{ fontSize: 15 }}>{m.label}</div>
                    <div className="panel-subtitle" style={{ marginBottom: 10 }}>{m.description}</div>
                    {m.status !== "Optimal" ? (
                      <div className="badge badge-bad" title="The pins plus the day's constraints admit no schedule under this objective.">infeasible — pins + constraints can't coexist</div>
                    ) : (
                      <>
                        {m.time_limited && (
                          <div className="badge badge-warn" style={{ marginBottom: 8 }} title="The solver stopped at the time limit; this is the best schedule found so far, not proven optimal.">
                            best found within time limit
                          </div>
                        )}
                        {emptyDueToFloors ? (
                          <div className="badge badge-warn" style={{ display: "block", padding: "8px 10px", fontSize: 12.5, whiteSpace: "normal", textAlign: "left" }}>
                            schedule is empty because the mission-share floors can't be met
                          </div>
                        ) : (
                          <>
                            <div style={{ fontSize: 26, fontWeight: 700 }}>
                              {m.satisfied_count}<span className="muted" style={{ fontSize: 14, fontWeight: 400 }}> / {result.customers_total} satisfied</span>
                            </div>
                            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
                              {m.deliveries_scheduled} missions · status {m.status}
                            </div>
                            <div style={{ marginTop: 8, fontSize: 12.5 }}>
                              {m.satisfied_ranks.length === 0
                                ? <span className="muted">no ranks covered</span>
                                : <>ranks {m.satisfied_ranks.map((r) => <span key={r} className="badge badge-good" style={{ marginRight: 3 }}>#{r}</span>)}</>}
                            </div>
                          </>
                        )}
                      </>
                    )}
                  </button>
                );
              })}
            </div>

            {selected && selected.status === "Optimal" && (
              <>
                <div className="panel">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <div className="panel-title">Customer outcomes — {selected.label}</div>
                    <div style={{ display: "flex", gap: 6 }}>
                      {Object.entries(selected.mission_counts_by_type).map(([t, n]) => (
                        <span key={t} className="badge badge-neutral">{t}: {n}</span>
                      ))}
                    </div>
                  </div>
                  <table style={{ marginTop: 10 }}>
                    <thead>
                      <tr><th>Rank</th><th>Customer</th><th>Type</th><th>Result</th><th>Option progress</th></tr>
                    </thead>
                    <tbody>
                      {selected.customers.map((c) => (
                        <tr key={c.customer_id}>
                          <td>#{c.rank}{c.pinned ? " 📌" : ""}</td>
                          <td>{c.label} <span className="muted">({c.customer_id})</span></td>
                          <td className="muted">{c.customer_type || "—"}</td>
                          <td>
                            <span className={`badge ${c.satisfied ? "badge-good" : "badge-bad"}`}>
                              {c.satisfied ? (c.satisfied_by ? `satisfied via ${c.satisfied_by}` : "satisfied") : "not satisfied"}
                            </span>
                          </td>
                          <td className="muted" style={{ fontSize: 12.5 }}>
                            {Object.keys(c.shortfall).length === 0 ? "—" :
                              Object.entries(c.shortfall).map(([k, sf]) => `${k}: ${sf.shipped}/${sf.needed}`).join(", ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="panel">
                  <div className="panel-title">Dispatch plan — {selected.label}</div>
                  {selected.dispatches.length === 0 ? (
                    <div className="muted" style={{ fontSize: 13.5 }}>No missions scheduled at this cap.</div>
                  ) : (
                    <table>
                      <thead>
                        <tr><th></th><th>Asset</th><th>From</th><th>Method</th><th>To</th><th>Refueler</th><th>Cargo</th></tr>
                      </thead>
                      <tbody>
                        {selected.dispatches.map((d, i) => (
                          <tr key={i}>
                            <td>{d.pinned ? <span className="badge badge-neutral" title="Includes a human-pinned decision">📌 manual</span> : <span className="muted" style={{ fontSize: 12 }}>auto</span>}</td>
                            <td>{d.asset_id}</td>
                            <td className="muted">{d.home_warehouse_id}</td>
                            <td className="muted">{d.method}</td>
                            <td>{d.customer_id}</td>
                            <td>{d.refueler_id ? <span className="badge badge-warn">{d.refueler_id}</span> : <span className="muted">—</span>}</td>
                            <td style={{ fontSize: 12.5 }}>
                              {Object.entries(d.cargo).map(([k, q]) => `${k}×${q}`).join(", ") || "—"}
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
        </>
      )}
    </div>
  );
}
