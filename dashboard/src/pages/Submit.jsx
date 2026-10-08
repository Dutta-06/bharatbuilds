import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { when } from "../time.js";
import { ErrorBox, Loading, PageHead, Readout } from "./common.jsx";

const GPUS = ["a100", "h100", "l4", "t4", "v100"];
const DEADLINES = [6, 12, 24, 48, 72];

/** The best window the 48 h forecast offers for this job, from the same /surface the Surface page shows.
 *  An estimate: it prices the job as one block of GPU-hours, and placement makes the exact plan. */
function estimate(data, form) {
  if (!data) return null;
  const duration = Math.max(1, Math.ceil(form.gpu_hours / form.gpus));
  const lastStart = Math.min(Math.floor(form.deadline_h) - duration, data.hours.length - 1);
  if (lastStart < 0) return { tooTight: duration };
  const baseRegion = data.regions.find((r) => r.id === form.submit_region);
  const base = baseRegion?.cells[0];
  let best = null;
  for (const r of data.regions) {
    if (form.allowed.length && !form.allowed.includes(r.id)) continue;
    if (form.data_residency && baseRegion && r.geo !== baseRegion.geo) continue;
    r.cells.slice(0, lastStart + 1).forEach((c) => { if (!best || c.cost < best.cell.cost) best = { region: r, cell: c }; });
  }
  return best && base ? { best, base } : null;
}

export default function Submit() {
  const [regions, setRegions] = useState([]);
  const [form, setForm] = useState({
    name: "", gpu_hours: 4, gpus: 1, gpu: "a100", deadline_h: 24, submit_region: "ap-south-1",
    water: 50, data_residency: false, allowed: [], splittable: false, max_chunks: 2,
  });
  const [preview, setPreview] = useState({ data: null, loading: true });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.regions().then(setRegions).catch(setError); }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const toggle = (id) => setForm((f) => ({ ...f, allowed: f.allowed.includes(id) ? f.allowed.filter((x) => x !== id) : [...f.allowed, id] }));
  const num = (v, d) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : d);

  // Re-price the preview shortly after the inputs settle.
  const key = [num(form.gpu_hours, 1), form.gpu, form.water, form.submit_region].join("|");
  useEffect(() => {
    let alive = true;
    setPreview((p) => ({ ...p, loading: true }));
    const t = setTimeout(() => {
      api.surface({ gpu_hours: num(form.gpu_hours, 1), gpu: form.gpu, w_water: form.water / 100, w_carbon: 1 - form.water / 100, baseline: form.submit_region })
        .then((data) => alive && setPreview({ data, loading: false }))
        .catch(() => alive && setPreview({ data: null, loading: false }));
    }, 350);
    return () => { alive = false; clearTimeout(t); };
  }, [key]);
  const est = useMemo(() => estimate(preview.data, { ...form, gpu_hours: num(form.gpu_hours, 1), gpus: num(form.gpus, 1), deadline_h: num(form.deadline_h, 24) }),
    [preview.data, form]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const job = await api.submit({
        name: form.name, gpu_hours: Number(form.gpu_hours), gpus: Number(form.gpus), gpu: form.gpu,
        deadline_h: Number(form.deadline_h), submit_region: form.submit_region,
        data_residency: form.data_residency,
        splittable: form.splittable, max_chunks: Number(form.max_chunks),
        allowed_regions: form.allowed.length ? form.allowed : undefined,
        weights: { water: form.water / 100, carbon: 1 - form.water / 100 },
      });
      window.location.hash = `#/jobs/${job.job_id}`;
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  const save = (a, b) => (a != null && b ? ((b - a) / b) * 100 : null);
  return (
    <>
      <PageHead title="Submit a job">
        Say how much work it is and when it has to be done. Pravaah picks the region and hour where cooling needs the
        least water and the grid is cleanest, runs it there, and gives you a receipt.
      </PageHead>
      <ErrorBox error={error} />
      <form onSubmit={submit} className="split submit-grid" id="job-form">
        <div className="stack fields" style={{ gap: 28 }}>
          <fieldset>
            <legend>Job</legend>
            <div className="field"><label className="lbl" htmlFor="name">Name <span className="muted">(optional)</span></label>
              <input id="name" type="text" value={form.name} onChange={set("name")} maxLength={80} placeholder="e.g. nightly fine-tune" /></div>
            <div className="cols" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
              <div className="field"><label className="lbl" htmlFor="gpu_hours">GPU-hours</label>
                <input id="gpu_hours" type="number" min="0.25" step="0.25" required value={form.gpu_hours} onChange={set("gpu_hours")} /></div>
              <div className="field"><label className="lbl" htmlFor="gpus">GPUs in parallel</label>
                <input id="gpus" type="number" min="1" step="1" value={form.gpus} onChange={set("gpus")} /></div>
              <div className="field"><label className="lbl" htmlFor="gpu">GPU type</label>
                <select id="gpu" value={form.gpu} onChange={set("gpu")}>{GPUS.map((g) => <option key={g} value={g}>{g.toUpperCase()}</option>)}</select></div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Timing</legend>
            <div className="field">
              <label className="lbl" htmlFor="deadline_h">Finish within (hours from now)</label>
              <div className="row">
                <input id="deadline_h" type="number" min="1" step="1" required value={form.deadline_h} onChange={set("deadline_h")} style={{ width: 110 }} />
                <div className="chips" role="group" aria-label="Deadline presets">
                  {DEADLINES.map((h) => <button key={h} type="button" className="chip" aria-pressed={Number(form.deadline_h) === h}
                    onClick={() => setForm((f) => ({ ...f, deadline_h: h }))}>{h} h</button>)}
                </div>
              </div>
              <span className="hint">More time gives the scheduler more hours to choose from, which usually means bigger savings.</span>
            </div>
          </fieldset>

          <fieldset>
            <legend>Priorities</legend>
            <div className="field">
              <label className="lbl" htmlFor="water">Optimise for</label>
              <input id="water" type="range" min="0" max="100" step="10" value={form.water} onChange={set("water")}
                aria-valuetext={`${form.water}% water, ${100 - form.water}% carbon`} />
              <div className="row small num" style={{ justifyContent: "space-between" }}>
                <span>carbon {100 - form.water}%</span><span>water {form.water}%</span>
              </div>
            </div>
            <div className="field"><label className="lbl" htmlFor="submit_region">Compare savings against</label>
              <select id="submit_region" value={form.submit_region} onChange={set("submit_region")}>
                {regions.map((r) => <option key={r.id} value={r.id}>{r.id} · {r.name}</option>)}
              </select>
              <span className="hint">Where you would run this job today, starting now. Savings are measured against that.</span></div>
          </fieldset>

          <fieldset>
            <legend>Constraints</legend>
            <label className="check"><input type="checkbox" checked={form.data_residency} onChange={set("data_residency")} />
              <span>Keep the job in the same jurisdiction as the comparison region <span className="muted">(data residency)</span></span></label>
            <details>
              <summary className="small" style={{ cursor: "pointer" }}>Advanced: limit regions, allow splitting</summary>
              <div className="stack" style={{ marginTop: 12 }}>
                <div className="field"><span className="lbl">Only these regions {form.allowed.length === 0 && <span className="muted">(all allowed)</span>}</span>
                  <div className="chips">{regions.map((r) => (
                    <label key={r.id} className="chip"><input type="checkbox" checked={form.allowed.includes(r.id)} onChange={() => toggle(r.id)} />{r.id}</label>))}</div></div>
                <label className="check"><input type="checkbox" checked={form.splittable} onChange={set("splittable")} />
                  <span>The job can checkpoint. Also show the best plan split into up to{" "}
                    <input type="number" min="1" max="6" value={form.max_chunks} onChange={set("max_chunks")} aria-label="Maximum chunks"
                      style={{ width: 56, height: 28, display: "inline-block" }} /> chunks.</span></label>
              </div>
            </details>
          </fieldset>

        </div>

        <aside className="panel stack estimate" aria-live="polite" aria-label="Estimate">
          <div className="section-title" style={{ margin: 0 }}>Estimate from the 48 h forecast</div>
          {preview.loading && !est && <Loading rows={3} />}
          {est?.tooTight && <p>This job needs {est.tooTight} h to run, so a deadline under {est.tooTight} h cannot be met.</p>}
          {!preview.loading && !est && <p className="muted">No forecast available to estimate from. You can still place the job.</p>}
          {est?.best && (
            <>
              <div>
                <div className="num" style={{ fontSize: 18, fontWeight: 500 }}>{est.best.region.id}</div>
                <div>{when(est.best.cell.hour)}</div>
                <div className="small muted">{est.best.region.name}</div>
              </div>
              <div className="stack" style={{ gap: 12, opacity: preview.loading ? 0.55 : 1 }}>
                <Readout label="Water" value={fmt.litres(est.best.cell.litres)} unit="L">
                  vs {fmt.litres(est.base.litres)} L now in {form.submit_region}
                  {" · "}<strong>{fmt.pct(save(est.best.cell.litres, est.base.litres))} {save(est.best.cell.litres, est.base.litres) >= 0 ? "less" : ""}</strong></Readout>
                <Readout label="Carbon" value={fmt.kg(est.best.cell.kg_co2)} unit="kg CO₂">
                  vs {fmt.kg(est.base.kg_co2)} kg
                  {" · "}<strong>{fmt.pct(save(est.best.cell.kg_co2, est.base.kg_co2))} {save(est.best.cell.kg_co2, est.base.kg_co2) >= 0 ? "less" : ""}</strong></Readout>
              </div>
              <p className="small muted">An estimate. Placement checks every region and hour before the deadline and shows its reasoning.</p>
            </>
          )}
        </aside>
        <div className="place"><button className="primary" disabled={busy} style={{ minWidth: 160 }}>{busy ? "Placing…" : "Place job"}</button></div>
      </form>
    </>
  );
}
