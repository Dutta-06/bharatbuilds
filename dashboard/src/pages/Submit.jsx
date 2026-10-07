import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorBox } from "./common.jsx";

const GPUS = ["a100", "h100", "l4", "t4", "v100"];

export default function Submit() {
  const [regions, setRegions] = useState([]);
  const [form, setForm] = useState({
    name: "", gpu_hours: 4, gpus: 1, gpu: "a100", deadline_h: 24, submit_region: "ap-south-1",
    water: 50, data_residency: false, allowed: [],
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.regions().then(setRegions).catch(setError); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const toggle = (id) => setForm({ ...form, allowed: form.allowed.includes(id) ? form.allowed.filter((x) => x !== id) : [...form.allowed, id] });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const job = await api.submit({
        name: form.name, gpu_hours: Number(form.gpu_hours), gpus: Number(form.gpus), gpu: form.gpu,
        deadline_h: Number(form.deadline_h), submit_region: form.submit_region,
        data_residency: form.data_residency,
        allowed_regions: form.allowed.length ? form.allowed : undefined,
        weights: { water: form.water / 100, carbon: 1 - form.water / 100 },
      });
      window.location.hash = `#/jobs/${job.job_id}`;
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <>
      <h1>Submit a job</h1>
      <p className="lede">Tell Pravaah how much work it is and when it must be done. It picks the region and hour
        where cooling needs the least water and the grid is cleanest, runs it there, and gives you a receipt.</p>
      <ErrorBox error={error} />
      <form className="card" onSubmit={submit}>
        <div className="grid2">
          <div>
            <label>Name (optional)<input type="text" value={form.name} onChange={set("name")} maxLength={80} /></label>
            <label>GPU-hours<input type="number" min="0.25" step="0.25" required value={form.gpu_hours} onChange={set("gpu_hours")} /></label>
            <label>GPUs in parallel<input type="number" min="1" step="1" value={form.gpus} onChange={set("gpus")} /></label>
            <label>GPU type<select value={form.gpu} onChange={set("gpu")}>{GPUS.map((g) => <option key={g}>{g}</option>)}</select></label>
          </div>
          <div>
            <label>Deadline: hours from now<input type="number" min="1" step="1" required value={form.deadline_h} onChange={set("deadline_h")} /></label>
            <label>Submitted from (baseline region)
              <select value={form.submit_region} onChange={set("submit_region")}>
                {regions.map((r) => <option key={r.id} value={r.id}>{r.id} · {r.name}</option>)}
              </select>
            </label>
            <label>Water vs carbon: <strong>{form.water}% water / {100 - form.water}% carbon</strong>
              <input type="range" min="0" max="100" step="10" value={form.water} onChange={set("water")} />
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={form.data_residency} onChange={set("data_residency")} />
              Data must stay in the same jurisdiction as the baseline region
            </label>
          </div>
        </div>
        <details>
          <summary className="small">Limit to specific regions</summary>
          <div className="chips" style={{ marginTop: 8 }}>
            {regions.map((r) => (
              <label key={r.id} className="chip" style={{ margin: 0 }}>
                <input type="checkbox" checked={form.allowed.includes(r.id)} onChange={() => toggle(r.id)} /> {r.id}
              </label>
            ))}
          </div>
        </details>
        <p><button className="primary" disabled={busy}>{busy ? "Placing…" : "Place job"}</button></p>
      </form>
    </>
  );
}
