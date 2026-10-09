const BASE = (import.meta.env.VITE_API_URL || "http://localhost:3000").replace(/\/$/, "");

async function call(path, options = {}) {
  let resp;
  try {
    resp = await fetch(BASE + path, {
      ...options,
      headers: { "content-type": "application/json", ...(options.headers || {}) },
    });
  } catch {
    throw new Error(`Can't reach the Tidewise API at ${BASE}. Is it running?`);
  }
  const text = await resp.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { /* non-JSON error */ }
  if (!resp.ok && resp.status !== 202) {
    throw new Error(body?.error || body?.message || `API error ${resp.status}`);
  }
  return { status: resp.status, body };
}

// Standard views (default weights, 1 or 4 GPU-hours) are published to S3 after every forecast run.
// Reading them keeps traffic bursts off Lambda; anything else, or any failure, uses the API.
const SURFACE_URL = (import.meta.env.VITE_SURFACE_URL || "").replace(/\/$/, "");
const STATIC_HOURS = new Set(["1", "4"]);

async function surface(q) {
  const keys = Object.keys(q);
  if (SURFACE_URL && keys.length === 1 && keys[0] === "gpu_hours" && STATIC_HOURS.has(String(q.gpu_hours))) {
    try {
      const resp = await fetch(`${SURFACE_URL}/gpu-hours-${q.gpu_hours}.json`);
      if (resp.ok) return await resp.json();
    } catch { /* fall through to the API */ }
  }
  return call("/surface?" + new URLSearchParams(q)).then((r) => r.body);
}

export const api = {
  base: BASE,
  regions: () => call("/regions").then((r) => r.body.regions),
  surface,
  savings: (q) => call("/savings?" + new URLSearchParams(q)).then((r) => r.body),
  submit: (job) => call("/jobs", { method: "POST", body: JSON.stringify(job) }).then((r) => r.body),
  jobs: () => call("/jobs?limit=100").then((r) => r.body.jobs),
  job: (id) => call(`/jobs/${encodeURIComponent(id)}`).then((r) => r.body),
  reschedule: (id) => call(`/jobs/${encodeURIComponent(id)}/reschedule`, { method: "POST", body: "{}" }).then((r) => r.body),
  receipt: (id) => call(`/jobs/${encodeURIComponent(id)}/receipt`),
};
