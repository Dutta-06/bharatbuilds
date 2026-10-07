import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { ErrorBox } from "./common.jsx";

function Bars({ title, unit, base, sched, format }) {
  const max = Math.max(base, sched, 1e-9);
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <div className="bars" role="table" aria-label={title}>
        {[["Run now, here", base, "var(--base-bar)"], ["Pravaah", sched, "var(--accent)"]].map(([label, v, color]) => (
          <div className="bar-row" role="row" key={label}>
            <span role="cell">{label}</span>
            <div className="bar-track" role="cell"><div className="bar" style={{ width: `${(100 * v) / max}%`, background: color }} /></div>
            <span role="cell" className="num" style={{ textAlign: "right" }}>{format(v)} {unit}</span>
          </div>
        ))}
      </div>
      {base > 0 && <p className="small" style={{ marginBottom: 0 }}>{(100 * (base - sched) / base).toFixed(0)}% less with Pravaah.</p>}
    </div>
  );
}

export default function Savings() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api.jobs().then(setJobs).catch(setError); }, []);
  const placed = (jobs || []).filter((j) => j.preview_receipt);
  const sum = (f) => placed.reduce((a, j) => a + f(j.preview_receipt), 0);
  const base = { l: sum((r) => r.baseline.litres), kg: sum((r) => r.baseline.kg_co2) };
  const sched = { l: sum((r) => r.chosen.litres), kg: sum((r) => r.chosen.kg_co2) };
  return (
    <>
      <h1>Savings</h1>
      <p className="lede">Totals over the {placed.length} placed jobs, compared with running each one immediately in the
        region it was submitted from. Modelled from placement-time forecasts.</p>
      <ErrorBox error={error} />
      {jobs && placed.length === 0 && <div className="card">No placed jobs yet.</div>}
      {placed.length > 0 && (
        <div className="grid2">
          <Bars title="Water" unit="L" base={base.l} sched={sched.l} format={fmt.litres} />
          <Bars title="Carbon" unit="kg CO₂" base={base.kg} sched={sched.kg} format={fmt.kg} />
        </div>
      )}
      <div className="card small muted">The trace replay (naive versus scheduled over a public cluster trace, with deadline
        hit rate and median delay) is Step 10 of the plan and will appear here.</div>
    </>
  );
}
