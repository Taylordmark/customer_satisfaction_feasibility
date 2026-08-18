import { useState } from "react";
import EntityTable from "../components/EntityTable";

const TABS = [
  { key: "warehouses", label: "Warehouses" },
  { key: "teams", label: "Transport Control Teams" },
  { key: "customer-types", label: "Customer Types" },
  { key: "allocation-policies", label: "Mission Allocation Policies" },
  { key: "customers", label: "Customers" },
  { key: "package-types", label: "Package Types" },
  { key: "method-specs", label: "Transport Methods" },
  { key: "method-restrictions", label: "Method Cargo Restrictions" },
  { key: "assets", label: "Transport Assets" },
  { key: "refuelers", label: "Refuelers" },
  { key: "warehouse-inventory", label: "Warehouse Inventory" },
  { key: "customer-bundle-items", label: "Customer Bundles" },
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
            { key: "warehouse_id", label: "Stationed At", type: "select", optionsEndpoint: "/api/warehouses/", optionValue: "id", optionLabel: "label", nullable: true },
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
          subtitle={'Minimum share of scheduled missions that must go to a customer type. E.g. target_pct = 0.40 means "at least 40% of missions go to this type."'}
          endpoint="/allocation-policies/"
          idField="id"
          columns={[
            { key: "customer_type_id", label: "Customer Type", type: "select", optionsEndpoint: "/api/customer-types/", optionValue: "id", optionLabel: "name" },
            { key: "target_pct", label: "Target Share (0-1)", type: "number", step: "0.01" },
          ]}
        />
      )}

      {tab === "customers" && (
        <EntityTable
          title="Customers"
          subtitle="Priority score = 0.6 × local weight + 0.4 × HQ weight."
          endpoint="/customers/"
          idField="id"
          columns={[
            { key: "id", label: "ID", type: "text", readOnlyOnEdit: true },
            { key: "label", label: "Label", type: "text" },
            { key: "lat", label: "Latitude", type: "number", step: "0.0001" },
            { key: "lon", label: "Longitude", type: "number", step: "0.0001" },
            { key: "w", label: "Local Priority (1-10)", type: "number" },
            { key: "h", label: "HQ Priority (1-10)", type: "number" },
            { key: "customer_type_id", label: "Type", type: "select", optionsEndpoint: "/api/customer-types/", optionValue: "id", optionLabel: "name", nullable: true },
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

      {tab === "method-restrictions" && (
        <EntityTable
          title="Method Cargo Restrictions"
          subtitle="A package type this method is NOT able to carry (e.g. Air can't carry Hazmat)."
          endpoint="/method-restrictions/"
          idField="id"
          columns={[
            { key: "method", label: "Method", type: "select", optionsEndpoint: "/api/method-specs/", optionValue: "method", optionLabel: "method" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/api/package-types/", optionValue: "id", optionLabel: "name" },
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
            { key: "home_warehouse_id", label: "Home Warehouse", type: "select", optionsEndpoint: "/api/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "method", label: "Method", type: "select", optionsEndpoint: "/api/method-specs/", optionValue: "method", optionLabel: "method" },
            { key: "team_id", label: "Owning Team", type: "select", optionsEndpoint: "/api/teams/", optionValue: "id", optionLabel: "name", nullable: true },
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
            { key: "home_warehouse_id", label: "Home Warehouse", type: "select", optionsEndpoint: "/api/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "team_id", label: "Owning Team", type: "select", optionsEndpoint: "/api/teams/", optionValue: "id", optionLabel: "name", nullable: true },
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
            { key: "warehouse_id", label: "Warehouse", type: "select", optionsEndpoint: "/api/warehouses/", optionValue: "id", optionLabel: "label" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/api/package-types/", optionValue: "id", optionLabel: "name" },
            { key: "qty", label: "Qty", type: "number" },
          ]}
        />
      )}

      {tab === "customer-bundle-items" && (
        <EntityTable
          title="Customer Bundles"
          subtitle="Which packages, and how many, fully satisfy each customer. A customer isn't satisfied until every line arrives."
          endpoint="/customer-bundle-items/"
          idField="id"
          columns={[
            { key: "customer_id", label: "Customer", type: "select", optionsEndpoint: "/api/customers/", optionValue: "id", optionLabel: "label" },
            { key: "package_type_id", label: "Package Type", type: "select", optionsEndpoint: "/api/package-types/", optionValue: "id", optionLabel: "name" },
            { key: "qty_needed", label: "Qty Needed", type: "number" },
          ]}
        />
      )}
    </div>
  );
}
