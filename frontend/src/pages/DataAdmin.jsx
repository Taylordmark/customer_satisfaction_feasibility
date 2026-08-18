import { useEffect, useState } from "react";
import EntityTable from "../components/EntityTable";
import { api } from "../api";

const SETTINGS_FIELDS = [
  { key: "cycle_hours", label: "Execution cycle (hours)", help: "The daily flying/driving/sailing-hour budget every vehicle gets." },
  { key: "handling_time_hours", label: "Handling time (hours)", help: "Fixed load/unload overhead added to every trip." },
  { key: "refuel_overhead_hours", label: "Refuel overhead (hours)", help: "Extra time a trip costs when it needs a refueler rendezvous." },
  { key: "default_daily_cap", label: "Default daily mission cap", help: "Starting value for the page-5 mission cap slider." },
];

function SettingsPanel() {
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get("/settings/").then(setDraft).catch((e) => setError(e.message));
  }, []);

  async function save() {
    setError(null);
    setSaved(false);
    try {
      const payload = Object.fromEntries(SETTINGS_FIELDS.map((f) => [f.key, Number(draft[f.key])]));
      setDraft(await api.put("/settings/", payload));
      setSaved(true);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="panel">
      <div className="panel-title">Solver Settings</div>
      <div className="panel-subtitle">Cycle-wide constants the feasibility pages and solver compute with. Edits apply to the next run — nothing is cached.</div>
      {error && <div className="error-banner">{error}</div>}
      {!draft && !error && <div className="loading-text">Loading…</div>}
      {draft && (
        <table>
          <thead>
            <tr><th>Setting</th><th>Value</th><th>What it does</th></tr>
          </thead>
          <tbody>
            {SETTINGS_FIELDS.map((f) => (
              <tr key={f.key}>
                <td>{f.label}</td>
                <td>
                  <input
                    className="table-input"
                    type="number"
                    value={draft[f.key] ?? ""}
                    onChange={(e) => { setSaved(false); setDraft({ ...draft, [f.key]: e.target.value }); }}
                  />
                </td>
                <td className="muted" style={{ fontSize: 12.5 }}>{f.help}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {draft && (
        <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn btn-primary btn-sm" onClick={save}>Save settings</button>
          {saved && <span className="badge badge-good">saved</span>}
        </div>
      )}
    </div>
  );
}

const TABS = [
  { key: "warehouses", label: "Warehouses" },
  { key: "teams", label: "Transport Control Teams" },
  { key: "customer-types", label: "Customer Types" },
  { key: "allocation-policies", label: "Mission Allocation Policies" },
  { key: "customers", label: "Customers" },
  { key: "package-types", label: "Package Types" },
  { key: "method-specs", label: "Transport Methods" },
  { key: "asset-restrictions", label: "Asset Cargo Restrictions" },
  { key: "assets", label: "Transport Assets" },
  { key: "refuelers", label: "Refuelers" },
  { key: "warehouse-inventory", label: "Warehouse Inventory" },
  { key: "customer-bundle-items", label: "Customer Bundles" },
  { key: "planned-missions", label: "Planned Missions" },
  { key: "settings", label: "Solver Settings" },
];

export default function DataAdmin() {
  const [tab, setTab] = useState("warehouses");

  return (
    <div>
      <div className="page-header">
        <h1>Data</h1>
        <p>Everything the feasibility pages compute from — warehouses, teams, customers, packages, transport, and refuelers. Edits here take effect immediately across all five assessment pages.</p>
      </div>

      <div className="data-nav-tabs">
        {TABS.map((t) => (
          <a
            key={t.key}
            className={`data-nav-tab ${tab === t.key ? "active" : ""}`}
            onClick={(e) => {
              e.preventDefault();
              setTab(t.key);
            }}
            href="#"
          >
            {t.label}
          </a>
        ))}
      </div>

      {tab === "warehouses" && (
        <EntityTable
          title="Warehouses"
          subtitle="Resource nodes: hold package inventory, and are the home base for transport assets and refuelers."
          endpoint="/warehouses/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "label", label: "Label", type: "text" },
            { key: "lat", label: "Latitude", type: "number", step: "0.0001" },
            { key: "lon", label: "Longitude", type: "number", step: "0.0001" },
          ]}
        />
      )}

      {tab === "teams" && (
        <EntityTable
          title="Transport Control Teams"
          subtitle="The organization that owns a set of transport assets and refuelers, and has the authority to task them."
          endpoint="/teams/"
          idField="id"
          columns={[
            { key: "name", label: "Name", type: "text" },
            { key: "warehouse_id", label: "Stationed At", type: "select", optionsEndpoint: "/warehouses/", optionValue: "id", optionLabel: "label", nullable: true },
            { key: "description", label: "Description", type: "text" },
          ]}
        />
      )}

      {tab === "customer-types" && (
        <EntityTable
          title="Customer Types"
          subtitle="Categories like Storefront, Warehouse, or FOB — used by mission allocation policies."
          endpoint="/customer-types/"
          idField="id"
          columns={[{ key: "name", label: "Name", type: "text" }]}
        />
      )}

      {tab === "allocation-policies" && (
        <EntityTable
          title="Mission Allocation Policies"
          subtitle={'Minimum share of scheduled missions that must go to a customer type. E.g. 40 means at least 40% of missions go to this type.'}
          endpoint="/allocation-policies/"
          idField="id"
          columns={[
            { key: "customer_type_id", label: "Customer Type", type: "select", optionsEndpoint: "/customer-types/", optionValue: "id", optionLabel: "name" },
            { key: "target_pct", label: "Target Share (%)", type: "number", step: "1", scale: 100 },
          ]}
        />
      )}

      {tab === "customers" && (
        <EntityTable
          title="Customers"
          subtitle="Priority rank: 1 = highest priority. The optimizer converts rank to weight (rank r of N gets weight N+1−r)."
          endpoint="/customers/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "label", label: "Label", type: "text" },
            { key: "lat", label: "Latitude", type: "number", step: "0.0001" },
            { key: "lon", label: "Longitude", type: "number", step: "0.0001" },
            { key: "priority_rank", label: "Priority Rank (1 = top)", type: "number" },
            { key: "included", label: "In Today's Plan", type: "checkbox" },
            { key: "customer_type_id", label: "Type", type: "select", optionsEndpoint: "/customer-types/", optionValue: "id", optionLabel: "name", nullable: true },
          ]}
        />
      )}

      {tab === "package-types" && (
        <EntityTable
          title="Package Types"
          subtitle="What can be shipped, and what it weighs / how much space it takes."
          endpoint="/package-types/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "name", label: "Name", type: "text" },
            { key: "weight", label: "Weight (lb)", type: "number" },
            { key: "volume", label: "Volume (ft³)", type: "number" },
          ]}
        />
      )}

      {tab === "method-specs" && (
        <EntityTable
          title="Transport Methods"
          subtitle="Default speed, capacity, and range for each transport method (Air / Ground / Sea)."
          endpoint="/method-specs/"
          idField="method"
          columns={[
            { key: "method", label: "Method", type: "text", readOnlyOnEdit: true },
            { key: "speed_mph", label: "Speed (mph)", type: "number" },
            { key: "weight_cap", label: "Weight Cap (lb)", type: "number" },
            { key: "vol_cap", label: "Volume Cap (ft³)", type: "number" },
            { key: "range_mi", label: "Range (mi)", type: "number" },
          ]}
        />
      )}

      {tab === "asset-restrictions" && (
        <EntityTable
          title="Asset Cargo Restrictions"
          subtitle="A package type this specific vehicle is NOT able to carry. Per-vehicle, not per method — two ships can differ."
          endpoint="/asset-restrictions/"
          idField="id"
          columns={[
            { key: "asset_id", label: "Asset", type: "select", optionsEndpoint: "/assets/", optionValue: "id", optionLabel: "id" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/package-types/", optionValue: "id", optionLabel: "name" },
          ]}
        />
      )}

      {tab === "assets" && (
        <EntityTable
          title="Transport Assets"
          subtitle="Individual vehicles. Point-to-point: launches from its home warehouse, delivers, returns to reload."
          endpoint="/assets/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "home_warehouse_id", label: "Home Warehouse", type: "select", optionsEndpoint: "/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "method", label: "Method", type: "select", optionsEndpoint: "/method-specs/", optionValue: "method", optionLabel: "method" },
            { key: "vehicle_type", label: "Vehicle Type", type: "text" },
            { key: "available", label: "In Service", type: "checkbox" },
            { key: "team_id", label: "Owning Team", type: "select", optionsEndpoint: "/teams/", optionValue: "id", optionLabel: "name", nullable: true },
          ]}
        />
      )}

      {tab === "refuelers" && (
        <EntityTable
          title="Refuelers"
          subtitle="Extend an asset's range if it can physically reach the rendezvous point in time."
          endpoint="/refuelers/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "home_warehouse_id", label: "Home Warehouse", type: "select", optionsEndpoint: "/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "vehicle_type", label: "Vehicle Type", type: "text" },
            { key: "available", label: "In Service", type: "checkbox" },
            { key: "team_id", label: "Owning Team", type: "select", optionsEndpoint: "/teams/", optionValue: "id", optionLabel: "name", nullable: true },
            { key: "extension_mi", label: "Range Extension (mi)", type: "number" },
            { key: "self_range_mi", label: "Self Range to Rendezvous (mi)", type: "number" },
          ]}
        />
      )}

      {tab === "warehouse-inventory" && (
        <EntityTable
          title="Warehouse Inventory"
          subtitle="Units of each package type on hand at each warehouse."
          endpoint="/warehouse-inventory/"
          idField="id"
          columns={[
            { key: "warehouse_id", label: "Warehouse", type: "select", optionsEndpoint: "/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/package-types/", optionValue: "id", optionLabel: "name" },
            { key: "qty", label: "Qty", type: "number" },
          ]}
        />
      )}

      {tab === "customer-bundle-items" && (
        <EntityTable
          title="Customer Bundles"
          subtitle="Package options per customer. Lines are alternatives — fully delivering any one option satisfies the customer."
          endpoint="/customer-bundle-items/"
          idField="id"
          columns={[
            { key: "customer_id", label: "Customer", type: "select", optionsEndpoint: "/customers/", optionValue: "id", optionLabel: "label" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/package-types/", optionValue: "id", optionLabel: "name" },
            { key: "qty_needed", label: "Qty Needed", type: "number" },
          ]}
        />
      )}

      {tab === "planned-missions" && (
        <EntityTable
          title="Planned Missions"
          subtitle="Human-pinned missions for today. Only Customer is required — anything left blank stays the optimizer's choice. Pins are hard constraints: they count against the cap and quotas, and conflicts make the run refuse with an explanation."
          endpoint="/planned-missions/"
          idField="id"
          columns={[
            { key: "customer_id", label: "Customer", type: "select", optionsEndpoint: "/customers/", optionValue: "id", optionLabel: "label" },
            { key: "asset_id", label: "Asset (optional)", type: "select", optionsEndpoint: "/assets/", optionValue: "id", optionLabel: "id", nullable: true },
            { key: "refueler_id", label: "Refueler (optional)", type: "select", optionsEndpoint: "/refuelers/", optionValue: "id", optionLabel: "id", nullable: true },
            { key: "package_type_id", label: "Option (optional)", type: "select", optionsEndpoint: "/package-types/", optionValue: "id", optionLabel: "name", nullable: true },
            { key: "source_warehouse_id", label: "Source (optional)", type: "select", optionsEndpoint: "/warehouses/", optionValue: "id", optionLabel: "label", nullable: true },
          ]}
        />
      )}

      {tab === "settings" && <SettingsPanel />}
    </div>
  );
}
