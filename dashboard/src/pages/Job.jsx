import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { ErrorBox, Status } from "./common.jsx";

function Pct({ v }) {
  if (v == null) return "–";
  return v >= 0 ? <span style={{ color: "var(--good)" }}>{v.toFixed(0)}% less</span>
    : <span style={{ color: "var(--bad)" }}>{(-v).toFixed(0)}% more</span>;
}

function Reschedule({ job, onMoved }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const go = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.reschedule(job.job_id);
      setMsg(r.rescheduled ? `Moved to ${r.to.region} at ${fmt.hour(r.to.start)} (about ${(100 * r.improvement).toFixed(0)}% better).`
        : "No better window right now within this job's constraints.");
      if (r.rescheduled) onMoved();
    } catch (e) { setMsg(String(e.message || e)); } finally { setBusy(false); }
  };
  return (
    <div className="card">
      <strong>Waiting to start.</strong> Forecasts keep changing; check whether a better window has opened.{" "}
      <button className="primary" onClick={go} disabled={busy}>{busy ? "Checking…" : "Move to the better slot"}</button>
      {msg && <p className="small" role="status" style={{ marginBottom: 0 }}>{msg}</p>}
    </div>
  );
}

export default function Job({ id }) {
  const [job, setJob] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const j = await api.job(id); if (!alive) return; setJob(j);
        const r = await api.receipt(id); if (alive) setReceipt(r.status === 200 ? r.body : null);
      } catch (e) { if (alive) setError(e); }
    };
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [id, tick]);

  if (error) return <ErrorBox error={error} />;
  if (!job) return <p className="muted">Loading…</p>;
  const p = job.placement;
  const view = receipt?.declared_job?.receipt || job.preview_receipt;
  return (
    <>
      <h1>{job.name || `Job ${job.job_id}`} <Status value={job.status} /></h1>
      <p className="lede">{job.request.gpu_hours} GPU-hours on {job.request.gpu.toUpperCase()}, due {fmt.hour(job.request.deadline.replace(/Z$/, ""))}.
        Submitted from {job.request.submit_region}.</p>
      <div className="card explain">{p.reason}</div>
      {job.status === "waiting" && <Reschedule job={job} onMoved={() => setTick((t) => t + 1)} />}
      {view && (
        <div className="grid2">
          <div className="card">
            <div className="muted small">Water</div>
            <div className="hero">{fmt.litres(view.chosen.litres)} L <small>vs {fmt.litres(view.baseline.litres)} L now, here</small></div>
            <div><Pct v={view.saved.litres_pct} /> · range {fmt.litres(view.chosen.litres_low)}–{fmt.litres(view.chosen.litres_high)} L</div>
          </div>
          <div className="card">
            <div className="muted small">Carbon</div>
            <div className="hero">{fmt.kg(view.chosen.kg_co2)} kg <small>vs {fmt.kg(view.baseline.kg_co2)} kg now, here</small></div>
            <div><Pct v={view.saved.kg_co2_pct} /> · range {fmt.kg(view.chosen.kg_low)}–{fmt.kg(view.chosen.kg_high)} kg</div>
          </div>
        </div>
      )}
      {p.feasible && (
        <div className="card scroll">
          <h2 style={{ marginTop: 0 }}>Options considered ({p.candidates_considered})</h2>
          <table>
            <thead><tr><th></th><th>Region</th><th>Start</th><th className="num">Delay</th><th className="num">Cost</th>
              <th className="num">Water (L)</th><th className="num">CO₂ (kg)</th></tr></thead>
            <tbody>
              {[["Chosen", p.chosen], ["Run now, here", p.baseline], ...p.alternatives.map((a) => ["Alternative", a])]
                .filter(([, o]) => o).map(([label, o], i) => (
                  <tr key={i} style={label === "Chosen" ? { fontWeight: 600 } : {}}>
                    <td>{label}</td><td>{o.region}</td><td className="small">{fmt.hour(o.start)}</td>
                    <td className="num">{o.delay_h} h</td><td className="num">{o.cost.toFixed(2)}</td>
                    <td className="num">{fmt.litres(o.litres)}</td><td className="num">{fmt.kg(o.kg_co2)}</td>
                  </tr>))}
            </tbody>
          </table>
        </div>
      )}
      {job.split_plan?.feasible && (
        <div className="card scroll">
          <h2 style={{ marginTop: 0 }}>Split plan (up to {job.split_plan.max_chunks} chunks, {job.split_plan.solver})</h2>
          <table>
            <thead><tr><th>Chunk</th><th>Region</th><th>Start</th><th>End</th><th className="num">Hours</th>
              <th className="num">Water (L)</th><th className="num">CO₂ (kg)</th></tr></thead>
            <tbody>{job.split_plan.chunks.map((c, i) => (
              <tr key={i}><td>{i + 1}</td><td>{c.region}</td><td className="small">{fmt.hour(c.start)}</td>
                <td className="small">{fmt.hour(c.end)}</td><td className="num">{c.hours}</td>
                <td className="num">{fmt.litres(c.litres)}</td><td className="num">{fmt.kg(c.kg_co2)}</td></tr>))}</tbody>
          </table>
          {job.split_plan.saved_vs_baseline && <p className="small">Versus running now, here:{" "}
            <Pct v={job.split_plan.saved_vs_baseline.litres_pct} /> water, <Pct v={job.split_plan.saved_vs_baseline.kg_co2_pct} /> CO₂.</p>}
          <p className="small muted">{job.split_plan.note}</p>
        </div>
      )}
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Receipt <a className="small" href={`#/receipt/${job.job_id}`}>share, export or print</a></h2>
        {!receipt && <p className="muted">{job.status === "infeasible" ? "This job was not run." :
          "The final receipt appears here once the job has run. The figures above are the modelled preview."}</p>}
        {receipt && (
          <>
            <p>Ran in <strong>{receipt.ran_in}</strong>{receipt.requested_region !== receipt.ran_in &&
              <> (requested {receipt.requested_region}; {receipt.launched_via}: the worker isn't deployed there)</>}.</p>
            <p className="small">Declared job energy: {receipt.declared_job.energy_basis}.</p>
            <p className="small">What actually ran: {receipt.proxy_run.what}. {receipt.proxy_run.wall_s} s wall, {receipt.proxy_run.cpu_s} s CPU,
              {" "}{receipt.proxy_run.epochs} epochs, {Number(receipt.proxy_run.energy_kwh).toExponential(2)} kWh ({receipt.proxy_run.energy_basis}).</p>
            <p className="small muted">{receipt.declared_job.receipt.note}</p>
          </>
        )}
      </div>
    </>
  );
}
