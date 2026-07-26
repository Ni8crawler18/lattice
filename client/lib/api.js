// Backend base URL resolution, in priority order:
//   1. ?api=<url> query param — repointable from the URL bar on stage
//   2. NEXT_PUBLIC_LATTICE_API — set per deployment
//   3. localhost:8077 in dev, Render URL otherwise
export function apiBase() {
  if (typeof window !== "undefined") {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q) return q.replace(/\/$/, "");
  }
  if (process.env.NEXT_PUBLIC_LATTICE_API) {
    return process.env.NEXT_PUBLIC_LATTICE_API.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" &&
      /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)) {
    return "http://127.0.0.1:8077";
  }
  return "https://lattice-api-96cn.onrender.com";
}

// API key resolution: ?key=<k> in the URL bar, then env, then the demo
// master key (acceptable exposure for a hackathon console; rotate after).
const DEV_KEY = "ltk_bf2f484e71fd93ff7ad5962424fca5d2";
export function apiKey() {
  if (typeof window !== "undefined") {
    const q = new URLSearchParams(window.location.search).get("key");
    if (q) return q;
  }
  return process.env.NEXT_PUBLIC_LATTICE_API_KEY || DEV_KEY;
}
export const apiHeaders = () => ({ "X-API-Key": apiKey() });

async function post(path, body) {
  const r = await fetch(apiBase() + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...apiHeaders() },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export const compareAddresses = (a, b) => post("/compare", { a, b });
export const fetchReal = async () => {
  const r = await fetch(apiBase() + "/real", { headers: apiHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

export const batchAddresses = (addresses) => post("/batch", { addresses });
export const parseAddress = (address) => post("/parse", { address });
export const submitCsvJob = async (csvText, label = "console-import") => {
  const r = await fetch(`${apiBase()}/jobs/csv?label=${encodeURIComponent(label)}`, {
    method: "POST", headers: { "Content-Type": "text/csv", ...apiHeaders() }, body: csvText,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
export const getJob = async (id) => {
  const r = await fetch(`${apiBase()}/jobs/${id}`, { headers: apiHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
export const getJobResults = async (id) => {
  const r = await fetch(`${apiBase()}/jobs/${id}/results`, { headers: apiHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};
export const jobCsvUrl = (id) => `${apiBase()}/jobs/${id}/results?format=csv&key=${encodeURIComponent(apiKey())}`;
export const listJobs = async () => {
  const r = await fetch(`${apiBase()}/jobs`, { headers: apiHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const d = await r.json();
  return Array.isArray(d) ? d : d.jobs || [];
};
