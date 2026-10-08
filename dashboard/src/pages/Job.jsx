import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { humanise, relative, utc, when } from "../time.js";
import { ErrorBox, Loading, PageHead, Readout, Status } from "./common.jsx";

function Pct({ v }) {
  if (v == null) return "–";
  return v >= 0 ? <b style={{ color: "var(--good)" }}>{v.toFixed(0)}% less</b> : <b style={{ color: "var(--bad)" }}>{(-v).toFixed(0)}% more</b>;
}

const ORDER = ["placed", "waiting", "running", "done"];

function Lifecycle({ job, receipt }) {
  const failed = ["failed", "infeasible"].includes(job.status);
  const at = failed ? 1 : Math.max(0, ORDER.indexOf(job.status));
  const start = job.placement?.chosen?.start;
  const labels = [
    ["Placed", `${relative(job.submitted_at)}`],
    ["Waiting", start ? `starts ${when(start)}` : ""],
    ["Running", receipt?.proxy_run?.started_at ? when(receipt.proxy_run.started_at) : ""],
    ["Done", receipt?.proxy_run?.finished_at ? when(receipt.proxy_run.finished_at) : ""],
  ];
  return (
    <ol className="steps" aria-label="Job progress">
      {labels.map(([name, note], i) => (
        <li key={name} className={failed && i === at ? "bad" : i <= at && !failed ? "on" : ""} aria-current={i === at ? "step" : undefined}>
          {failed && i === at ? (job.status === "infeasible" ? "Not placed" : "Failed") : name}<small>{note}</small></li>))}
    </ol>
  );
}

function Reschedule({ job, onMoved }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const go = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.reschedule(job.job_id);
      setMsg(r.rescheduled ? `Moved to ${r.to.region}, ${when(r.to.start)} (about ${(100 * r.improvement).toFixed(0)}% cheaper).`
        : "No better window right now, within this job's constraints.");
      if (r.rescheduled) onMoved();
    } catch (e) { setMsg(String(e.message || e)); } finally { setBusy(false); }
  };
  return (
    <div className="panel row" style={{ justifyContent: "space-between" }}>
      <div style={{ maxWidth: "56ch" }}><b>Waiting to start.</b> <span className="muted">Forecasts change every hour. Check whether a better window has opened.</span>
        {msg && <p className="small" role="status" style={{ marginTop: 6 }}>{msg}</p>}</div>
      <button className="primary" onClick={go} disabled={busy}>{busy ? "Checking…" : "Move to the better slot"}</button>
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
  if (!job) return <Loading rows={5} />;
  const p = job.placement;
  const view = receipt?.declared_job?.receipt || job.preview_receipt;
  return (
    <>
      <PageHead eyebrow={job.name ? <>Job <span className="num">{job.job_id}</span></> : "Job"} title={<>{job.name || <span className="num">{job.job_id}</span>} <Status value={job.status} /></>}>
        {job.request.gpu_hours} GPU-hours on {job.request.gpu.toUpperCase()}, due {when(job.request.deadline)}.
        Submitted from {job.request.submit_region}{job.team ? `, team ${job.team}` : ""}.
      </PageHead>
      <Lifecycle job={job} receipt={receipt} />
      {job.status === "waiting" && <Reschedule job={job} onMoved={() => setTick((t) => t + 1)} />}
      <p className="explain">{humanise(p.reason)}</p>
      {view && (
        <div className="readouts">
          <Readout label="Water" value={fmt.litres(view.chosen.litres)} unit="L">
            <Pct v={view.saved.litres_pct} /> than {fmt.litres(view.baseline.litres)} L running now at {job.request.submit_region}
            <div className="small muted num">range {fmt.litres(view.chosen.litres_low)}–{fmt.litres(view.chosen.litres_high)} L</div></Readout>
          <Readout label="Carbon" value={fmt.kg(view.chosen.kg_co2)} unit="kg CO₂">
            <Pct v={view.saved.kg_co2_pct} /> than {fmt.kg(view.baseline.kg_co2)} kg running now
            <div className="small muted num">range {fmt.kg(view.chosen.kg_low)}–{fmt.kg(view.chosen.kg_high)} kg</div></Readout>
        </div>
      )}
      {p.feasible && (
        <section>
          <div className="section-title">Options considered ({p.candidates_considered})</div>
          <div className="panel tight scroll">
            <table>
              <thead><tr><th>Option</th><th>Region</th><th>Start</th><th className="num">Delay</th><th className="num">Cost</th><th className="num">Water L</th><th className="num">CO₂ kg</th></tr></thead>
              <tbody>
                {[["Chosen", p.chosen], ["Run now, here", p.baseline], ...p.alternatives.map((a) => ["Alternative", a])]
                  .filter(([, o]) => o).map(([label, o], i) => (
                    <tr key={i} style={label === "Chosen" ? { fontWeight: 600 } : {}}>
                      <td>{label}</td><td className="mono">{o.region}</td><td className="small nowrap" title={utc(o.start)}>{when(o.start)}</td>
                      <td className="num">{o.delay_h} h</td><td className="num">{o.cost.toFixed(2)}</td>
                      <td className="num">{fmt.litres(o.litres)}</td><td className="num">{fmt.kg(o.kg_co2)}</td>
                    </tr>))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {job.split_plan?.feasible && (
        <section>
          <div className="section-title">Split plan: up to {job.split_plan.max_chunks} chunks ({job.split_plan.solver})</div>
          <div className="panel tight scroll">
            <table>
              <thead><tr><th>Chunk</th><th>Region</th><th>Start</th><th>End</th><th className="num">Hours</th><th className="num">Water L</th><th className="num">CO₂ kg</th></tr></thead>
              <tbody>{job.split_plan.chunks.map((c, i) => (
                <tr key={i}><td className="num">{i + 1}</td><td className="mono">{c.region}</td><td className="small nowrap">{when(c.start)}</td>
                  <td className="small nowrap">{when(c.end)}</td><td className="num">{c.hours}</td>
                  <td className="num">{fmt.litres(c.litres)}</td><td className="num">{fmt.kg(c.kg_co2)}</td></tr>))}</tbody>
            </table>
          </div>
          {job.split_plan.saved_vs_baseline && <p className="small" style={{ marginTop: 8 }}>Against running now, here: <Pct v={job.split_plan.saved_vs_baseline.litres_pct} /> water, <Pct v={job.split_plan.saved_vs_baseline.kg_co2_pct} /> CO₂.</p>}
          <p className="small muted">{job.split_plan.note}</p>
        </section>
      )}
      <section className="rule-top">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <div className="section-title" style={{ margin: 0 }}>Receipt</div>
          <a className="btn" href={`#/receipt/${job.job_id}`}>Share, export or print</a>
        </div>
        {!receipt && <p className="muted">{job.status === "infeasible" ? "This job was not run." : "The final receipt appears here once the job has run. The figures above are the modelled preview from placement time."}</p>}
        {receipt && (
          <dl className="kv">
            <dt>Ran in</dt><dd><b className="num">{receipt.ran_in}</b>{receipt.requested_region !== receipt.ran_in && <> (requested {receipt.requested_region}; {receipt.launched_via}, because the worker is not deployed there)</>}</dd>
            <dt>Job energy</dt><dd>Estimated from GPU power draw, utilisation and facility overhead. This sets the water and carbon figures above.</dd>
            <dt>Stand-in run</dt><dd>{receipt.proxy_run.what}: {receipt.proxy_run.wall_s} s wall, {receipt.proxy_run.cpu_s} s CPU, {receipt.proxy_run.epochs} epochs,
              {" "}<span className="num">{Number(receipt.proxy_run.energy_kwh).toExponential(2)} kWh</span> measured from CPU time.</dd>
            <dt>Reading it</dt><dd className="muted">{receipt.declared_job.receipt.note}</dd>
          </dl>
        )}
      </section>
    </>
  );
}
