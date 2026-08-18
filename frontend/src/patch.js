// Small local PATCH helper mirroring api.js's request/error-handling pattern.
// api.js is owned by another agent and only exposes get/post/put/del, so
// partial-update (PATCH) calls live here instead of being added there.
const BASE = "/api";

function formatDetail(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const loc = Array.isArray(e.loc) ? e.loc : [];
        const field = loc.filter((seg, i) => !(i === 0 && seg === "body")).join(".");
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join("; ");
  }
  return detail;
}

export async function patch(path, data) {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = formatDetail(body.detail) || detail;
    } catch {
      // ignore — no JSON body
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}
