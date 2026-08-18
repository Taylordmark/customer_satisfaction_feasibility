import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

/**
 * columns: [{
 *   key, label,
 *   type: 'text' | 'number' | 'select',
 *   optionsEndpoint?: string,   // for type='select', fetched once
 *   optionValue?: string,       // field on the option object used as the value
 *   optionLabel?: string,       // field on the option object shown to the user
 *   nullable?: bool,            // select allows an empty/"none" choice
 *   step?: string,              // for number inputs, e.g. "0.01"
 *   readOnlyOnEdit?: bool,      // e.g. primary keys
 * }]
 */
export default function EntityTable({ title, subtitle, endpoint, columns, idField = "id" }) {
  const [items, setItems] = useState([]);
  const [optionsMap, setOptionsMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState({});
  const [adding, setAdding] = useState(false);
  const [newDraft, setNewDraft] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get(`${endpoint}`);
      setItems(data);
      const optEntries = await Promise.all(
        columns
          .filter((c) => c.type === "select" && c.optionsEndpoint)
          .map(async (c) => [c.key, await api.get(c.optionsEndpoint)])
      );
      setOptionsMap(Object.fromEntries(optEntries));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint, columns]);

  useEffect(() => {
    load();
  }, [load]);

  function emptyDraft() {
    const d = {};
    columns.forEach((c) => {
      d[c.key] = c.type === "number" ? "" : "";
    });
    return d;
  }

  function startAdd() {
    setNewDraft(emptyDraft());
    setAdding(true);
  }

  function castValue(col, raw) {
    if (raw === "" || raw === null || raw === undefined) return col.nullable ? null : raw;
    if (col.type === "number") return Number(raw);
    return raw;
  }

  async function saveNew() {
    setError(null);
    const payload = {};
    columns.forEach((c) => (payload[c.key] = castValue(c, newDraft[c.key])));
    try {
      await api.post(`${endpoint}`, payload);
      setAdding(false);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function startEdit(item) {
    setEditingId(item[idField]);
    const d = {};
    columns.forEach((c) => (d[c.key] = item[c.key] ?? ""));
    setDraft(d);
  }

  async function saveEdit(item) {
    setError(null);
    const payload = {};
    columns.forEach((c) => (payload[c.key] = castValue(c, draft[c.key])));
    try {
      await api.put(`${endpoint}${item[idField]}`, payload);
      setEditingId(null);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(item) {
    if (!confirm(`Delete ${item[idField]}? This can't be undone.`)) return;
    setError(null);
    try {
      await api.del(`${endpoint}${item[idField]}`);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function displayValue(col, value) {
    if (col.type === "select" && optionsMap[col.key]) {
      const opt = optionsMap[col.key].find((o) => String(o[col.optionValue]) === String(value));
      return opt ? opt[col.optionLabel] : value === null || value === undefined ? "—" : value;
    }
    if (value === null || value === undefined || value === "") return "—";
    return String(value);
  }

  function renderInput(col, value, onChange, isEditRow) {
    if (col.type === "select") {
      const opts = optionsMap[col.key] || [];
      return (
        <select className="table-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          {col.nullable && <option value="">— none —</option>}
          {opts.map((o) => (
            <option key={o[col.optionValue]} value={o[col.optionValue]}>
              {o[col.optionLabel]}
            </option>
          ))}
        </select>
      );
    }
    return (
      <input
        className="table-input"
        type={col.type === "number" ? "number" : "text"}
        step={col.step}
        value={value ?? ""}
        disabled={isEditRow && col.readOnlyOnEdit}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  return (
    <div className="panel">
      <div className="panel-title">{title}</div>
      {subtitle && <div className="panel-subtitle">{subtitle}</div>}
      {error && <div className="error-banner">{error}</div>}
      {loading ? (
        <div className="loading-text">Loading…</div>
      ) : (
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
              <th style={{ width: 120 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isEditing = editingId === item[idField];
              return (
                <tr key={item[idField]}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {isEditing
                        ? renderInput(c, draft[c.key], (v) => setDraft({ ...draft, [c.key]: v }), true)
                        : displayValue(c, item[c.key])}
                    </td>
                  ))}
                  <td>
                    {isEditing ? (
                      <div className="row-actions">
                        <button className="btn btn-primary btn-sm" onClick={() => saveEdit(item)}>Save</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditingId(null)}>Cancel</button>
                      </div>
                    ) : (
                      <div className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => startEdit(item)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => remove(item)}>Delete</button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {adding && (
              <tr>
                {columns.map((c) => (
                  <td key={c.key}>{renderInput(c, newDraft[c.key], (v) => setNewDraft({ ...newDraft, [c.key]: v }), false)}</td>
                ))}
                <td>
                  <div className="row-actions">
                    <button className="btn btn-primary btn-sm" onClick={saveNew}>Add</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setAdding(false)}>Cancel</button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
      {!adding && (
        <div style={{ marginTop: 14 }}>
          <button className="btn btn-primary btn-sm" onClick={startAdd}>+ Add row</button>
        </div>
      )}
    </div>
  );
}
