// Compatibility model for the manual-mission (pin) builder on page 5.
//
// Built from the page-3 and page-4 feasibility responses, it answers: given
// the fields already chosen (in any order), which values remain valid for
// each other field? A combination is "valid" when at least one in-service
// vehicle could actually fly it: reaches the customer (directly or with an
// in-service refueler), carries the option, is based at the source, and —
// for a source — the warehouse fully covers an option's quantity, since a
// source pin forces the whole delivery from that one warehouse.
//
// Cycle-time fit is not known client-side; the solver's pin validation
// remains the final authority.

export const PIN_FIELDS = [
  "customer_id",
  "package_type_id",
  "asset_id",
  "refueler_id",
  "source_warehouse_id",
];

export function buildPinModel(page3, page4) {
  const model = {};
  for (const entry of page4.per_customer) {
    const assets = {};
    for (const a of entry.direct_assets) {
      if (a.available === false) continue;
      assets[a.asset_id] = {
        direct: true,
        carries: new Set(a.carries),
        refuelers: [],
        warehouse_id: a.warehouse_id,
      };
    }
    for (const a of entry.supported_assets) {
      if (a.available === false) continue;
      const fs = (a.refuelers || [])
        .filter((f) => f.available !== false)
        .map((f) => f.refueler_id);
      if (fs.length === 0) continue;
      assets[a.asset_id] = {
        direct: false,
        carries: new Set(a.carries),
        refuelers: fs,
        warehouse_id: a.warehouse_id,
      };
    }
    model[entry.customer_id] = { assets, bundle: new Set(), sources: {} };
  }
  for (const entry of page3) {
    const m = model[entry.customer_id];
    if (!m) continue;
    for (const p of entry.packages) {
      m.bundle.add(p.package_type_id);
      m.sources[p.package_type_id] = new Set(
        p.warehouses.filter((w) => w.feasible).map((w) => w.warehouse_id)
      );
    }
  }
  return model;
}

// Could some in-service vehicle fly a pin like `sel` for customer `cid`?
// Empty-string fields are wildcards.
export function pinWorks(model, cid, sel) {
  const m = model[cid];
  if (!m) return false;
  const { asset_id: aid, package_type_id: k, refueler_id: f, source_warehouse_id: w } = sel;
  if (k && !m.bundle.has(k)) return false;
  const anyAsset = Object.entries(m.assets).some(([id, a]) =>
    (!aid || id === aid) &&
    (!k || a.carries.has(k)) &&
    (!w || a.warehouse_id === w) &&
    (!f || (!a.direct && a.refuelers.includes(f)))
  );
  if (!anyAsset) return false;
  if (w) {
    const options = k ? [k] : [...m.bundle];
    if (!options.some((kk) => m.sources[kk]?.has(w))) return false;
  }
  return true;
}

// Valid values for `field` given every other current selection. When no
// customer is chosen yet, a value is valid if it works for ANY included
// customer — so fields can be picked in any order.
export function validOptions(model, includedCustomerIds, draft, field, domain) {
  const base = { ...draft, [field]: "" };
  return domain.filter((v) => {
    const sel = { ...base, [field]: v };
    if (field === "customer_id") return pinWorks(model, v, sel);
    if (sel.customer_id) return pinWorks(model, sel.customer_id, sel);
    return includedCustomerIds.some((cid) => pinWorks(model, cid, sel));
  });
}

// Defensive cleanup: clear any selection that no longer fits the others
// (never clearing `keepField`, the one the user just changed).
export function normalizeDraft(model, includedCustomerIds, draft, domains, keepField) {
  let d = { ...draft };
  for (let pass = 0; pass < PIN_FIELDS.length; pass++) {
    let changed = false;
    for (const field of PIN_FIELDS) {
      if (field === keepField || !d[field]) continue;
      const valid = validOptions(model, includedCustomerIds, d, field, domains[field]);
      if (!valid.includes(d[field])) {
        d = { ...d, [field]: "" };
        changed = true;
      }
    }
    if (!changed) break;
  }
  return d;
}
