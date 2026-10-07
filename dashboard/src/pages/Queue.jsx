import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { ErrorBox, Status } from "./common.jsx";

export default function Queue() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch(setError);
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);
  return (
    <>
      <h1>Queue</h1>
      <p className="lede">Every job, newest first. Refreshes every 10 seconds.</p>
      <ErrorBox error={error} />
      {jobs && jobs.length === 0 && <div className="card">No jobs yet. <a href="#/submit">Submit one.</a></div>}
      {jobs && jobs.length > 0 && (
        <div className="card scroll">
          <table>
            <thead><tr><th>Job</th><th>Status</th><th className="num">GPU-h</th><th>From</th><th>Placed in</th>
              <th>Starts</th><th className="num">Water saved</th><th className="num">CO₂ saved</th></tr></thead>
            <tbody>
              {jobs.map((j) => {
                const c = j.placement?.chosen; const s = j.preview_receipt?.saved;
                return (
                  <tr key={j.job_id}>
                    <td><a href={`#/jobs/${j.job_id}`}>{j.name || j.job_id}</a></td>
                    <td><Status value={j.status} /></td>
                    <td className="num">{j.request.gpu_hours}</td>
                    <td>{j.request.submit_region}</td>
                    <td>{c?.region || "–"}</td>
                    <td className="small">{c ? fmt.hour(c.start) : "–"}</td>
                    <td className="num">{s ? `${fmt.litres(s.litres)} L` : "–"}</td>
                    <td className="num">{s ? `${fmt.kg(s.kg_co2)} kg` : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
