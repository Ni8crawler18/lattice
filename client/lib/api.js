// The console holds no API key.
//
// Every data call goes to same-origin /api/lattice/*, which is a server-side
// route that checks the session and attaches the key itself. Nothing secret is
// ever shipped to the browser, so there is no key to find in the bundle and
// none to rotate when someone reads it.
//
// `apiBase()` is now display-only: the public URL we print in curl examples and
// docs. It is deliberately NOT where the console sends its own requests.

export function apiBase() {
  if (typeof window !== "undefined") {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q) return q.replace(/\/$/, "");
  }
  if (process.env.NEXT_PUBLIC_LATTICE_API) {
    return process.env.NEXT_PUBLIC_LATTICE_API.replace(/\/$/, "");
  }
  return "https://lattice-api-fs5f.onrender.com";
}

// Where the console's own fetches go. Same origin, no credentials in the URL.
export const proxyBase = () => "/api/lattice";

async function post(path, body) {
  const r = await fetch(proxyBase() + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export const compareAddresses = (a, b) => post("/compare", { a, b });
export const fetchReal = async () => {
  const r = await fetch(proxyBase() + "/real");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

export const batchAddresses = (addresses) => post("/batch", { addresses });
export const parseAddress = (address) => post("/parse", { address });
export const submitCsvJob = async (csvText, label = "console-import") => {
  const r = await fetch(`${proxyBase()}/jobs/csv?label=${encodeURIComponent(label)}`, {
    method: "POST", headers: { "Content-Type": "text/csv" }, body: csvText,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
export const getJob = async (id) => {
  const r = await fetch(`${proxyBase()}/jobs/${id}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
export const getJobResults = async (id) => {
  const r = await fetch(`${proxyBase()}/jobs/${id}/results`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
// The download link is same-origin too, so no key rides along in the URL.
export const jobCsvUrl = (id) => `${proxyBase()}/jobs/${id}/results?format=csv`;
export const listJobs = async () => {
  const r = await fetch(`${proxyBase()}/jobs`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = await r.json();
  return Array.isArray(d) ? d : d.jobs || [];
};
