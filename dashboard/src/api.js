const BASE = (import.meta.env.VITE_API_URL || "http://localhost:3000").replace(/\/$/, "");

async function call(path, options = {}) {
  let resp;
  try {
    resp = await fetch(BASE + path, {
      ...options,
      headers: { "content-type": "application/json", ...(options.headers || {}) },
    });
  } catch {
    throw new Error(`Can't reach the Pravaah API at ${BASE}. Is it running?`);
  }
  const text = await resp.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { /* non-JSON error */ }
  if (!resp.ok && resp.status !== 202) {
    throw new Error(body?.error || body?.message || `API error ${resp.status}`);
  }
  return { status: resp.status, body };
}

export const api = {
  base: BASE,
  regions: () => call("/regions").then((r) => r.body.regions),
  surface: (q) => call("/surface?" + new URLSearchParams(q)).then((r) => r.body),
  submit: (job) => call("/jobs", { method: "POST", body: JSON.stringify(job) }).then((r) => r.body),
  jobs: () => call("/jobs?limit=100").then((r) => r.body.jobs),
  job: (id) => call(`/jobs/${encodeURIComponent(id)}`).then((r) => r.body),
  receipt: (id) => call(`/jobs/${encodeURIComponent(id)}/receipt`),
};
