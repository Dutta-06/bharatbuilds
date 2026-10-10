import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { relative, when } from "../time.js";
import { Empty, ErrorBox, Loading, PageHead, Status } from "./common.jsx";

const FILTERS = [["all", "All"], ["waiting", "Waiting"], ["deferred", "Deferred"], ["running", "Running"], ["done", "Done"], ["failed", "Failed"]];

export default function Queue() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch(setError);
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);
  const counts = useMemo(() => {
    const c = { all: jobs?.length || 0 };
    (jobs || []).forEach((j) => { const k = j.status === "infeasible" ? "failed" : j.status; c[k] = (c[k] || 0) + 1; });
    return c;
  }, [jobs]);
  const shown = (jobs || []).filter((j) => filter === "all" || (filter === "failed" ? ["failed", "infeasible"].includes(j.status) : j.status === filter));
  return (
    <>
      <PageHead eyebrow="Live, refreshes every 10 s" title="Queue">Every job, newest first, with where it will run and what the placement saves compared with running it right away.</PageHead>
      <ErrorBox error={error} />
      {!jobs && !error && <Loading rows={4} />}
      {jobs && jobs.length === 0 && <Empty title="No jobs yet"><a className="btn primary" href="#/submit">Submit the first job</a></Empty>}
      {jobs && jobs.length > 0 && (
        <section className="stack">
          <div className="chips" role="group" aria-label="Filter by status">
            {FILTERS.filter(([k]) => k === "all" || counts[k]).map(([k, label]) => (
              <button key={k} type="button" className="chip" aria-pressed={filter === k} onClick={() => setFilter(k)}>{label} <span className="num">{counts[k] || 0}</span></button>))}
          </div>
          <div className="panel tight">
            <div className="scroll jobtable">
              <table>
                <thead><tr><th>Job</th><th>Status</th><th className="num">GPU-h</th><th>Route</th><th>Starts</th>
                  <th className="num">Water saved</th><th className="num">CO₂ saved</th></tr></thead>
                <tbody>
                  {shown.map((j) => {
                    const c = j.placement?.chosen; const s = j.preview_receipt?.saved;
                    return (
                      <tr key={j.job_id}>
                        <td><a href={`#/jobs/${j.job_id}`}>{j.name || <span className="num">{j.job_id}</span>}</a>{j.team && <span className="muted small"> · {j.team}</span>}</td>
                        <td><Status value={j.status} /></td>
                        <td className="num">{j.request.gpu_hours ?? 'SIMULATED'}</td>
                        <td className="mono">{j.execution_mode === 'SIMULATED_FACILITY' ? j.facility_id : <>{j.request.submit_region} → <b>{c?.region || "–"}</b></>}</td>
                        <td className="small nowrap" title={c?.start && relative(c.start)}>{c ? when(c.start) : "–"}</td>
                        <td className="num">{s ? `${fmt.litres(s.litres)} L` : "–"}</td>
                        <td className="num">{s ? `${fmt.kg(s.kg_co2)} kg` : "–"}</td>
                      </tr>);
                  })}
                </tbody>
              </table>
            </div>
            <div className="joblist">
              {shown.map((j) => {
                const c = j.placement?.chosen; const s = j.preview_receipt?.saved;
                return (
                  <a className="job" href={`#/jobs/${j.job_id}`} key={j.job_id}>
                    <div className="top"><b>{j.name || <span className="num">{j.job_id}</span>}</b><Status value={j.status} /></div>
                    <div className="route">{j.execution_mode === 'SIMULATED_FACILITY' ? `SIMULATED · ${j.facility_id} · ${j.estimated_power_kw} kW` : `${j.request.submit_region} → ${c?.region || '–'} · ${j.request.gpu_hours} GPU-h`}</div>
                    <div className="small">{c ? `Starts ${when(c.start)}` : "Not placed"}</div>
                    {s && <div className="save num">{fmt.litres(s.litres)} L water · {fmt.kg(s.kg_co2)} kg CO₂ saved</div>}
                  </a>);
              })}
            </div>
            {shown.length === 0 && <p className="muted" style={{ padding: 20 }}>No {filter} jobs.</p>}
          </div>
        </section>
      )}
    </>
  );
}
