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

function Replay({ data }) {
  const h = data.headline;
  const ww = data.when_vs_where;
  return (
    <>
      <h2>Trace replay: {h.jobs} jobs</h2>
      <div className="banner small" role="note">
        <strong>Read with the assumptions:</strong>
        <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{data.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </div>
      <div className="grid2">
        <Bars title="Water, whole queue" unit="L" base={h.naive.litres} sched={h.pravaah.litres} format={fmt.litres} />
        <Bars title="Carbon, whole queue" unit="kg CO₂" base={h.naive.kg_co2} sched={h.pravaah.kg_co2} format={fmt.kg} />
      </div>
      <div className="grid2">
        <div className="card"><div className="muted small">Deadlines met</div><div className="hero">{h.deadline_hit_rate_pct}%</div></div>
        <div className="card"><div className="muted small">Median delay</div><div className="hero">{h.median_delay_h} h</div></div>
        <div className="card"><div className="muted small">Jobs moved to another region</div><div className="hero">{h.moved_region_pct}%</div></div>
      </div>
      <div className="card scroll">
        <h2 style={{ marginTop: 0 }}>When versus where</h2>
        <table>
          <thead><tr><th>Scenario</th><th className="num">Water saved</th><th className="num">CO₂ saved</th><th className="num">Median delay</th></tr></thead>
          <tbody>
            <tr><td>Time-shift only (stay in submit region)</td><td className="num">{ww.time_only_same_region.saved_pct.litres}%</td>
              <td className="num">{ww.time_only_same_region.saved_pct.kg_co2}%</td><td className="num">{ww.time_only_same_region.median_delay_h} h</td></tr>
            <tr><td>Time and region (Pravaah)</td><td className="num">{ww.time_and_region.saved_pct.litres}%</td>
              <td className="num">{ww.time_and_region.saved_pct.kg_co2}%</td><td className="num">{ww.time_and_region.median_delay_h} h</td></tr>
          </tbody>
        </table>
      </div>
      <div className="grid2">
        <div className="card scroll">
          <h2 style={{ marginTop: 0 }}>Deadline slack</h2>
          <table>
            <thead><tr><th>Slack beyond job length</th><th className="num">Water saved</th><th className="num">CO₂ saved</th></tr></thead>
            <tbody>{data.slack_sensitivity.map((r) => (
              <tr key={r.extra_slack_h}><td>+{r.extra_slack_h} h</td><td className="num">{r.saved_pct.litres}%</td><td className="num">{r.saved_pct.kg_co2}%</td></tr>))}</tbody>
          </table>
        </div>
        <div className="card scroll">
          <h2 style={{ marginTop: 0 }}>Weights</h2>
          <table>
            <thead><tr><th>Optimising for</th><th className="num">Water saved</th><th className="num">CO₂ saved</th></tr></thead>
            <tbody>{data.weight_sensitivity.map((r) => (
              <tr key={r.weights}><td>{r.weights}</td><td className="num">{r.saved_pct.litres}%</td><td className="num">{r.saved_pct.kg_co2}%</td></tr>))}</tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export default function Savings() {
  const [jobs, setJobs] = useState(null);
  const [replay, setReplay] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.jobs().then(setJobs).catch(setError);
    fetch(`${import.meta.env.BASE_URL}replay.json`).then((r) => (r.ok ? r.json() : null)).then(setReplay).catch(() => setReplay(null));
  }, []);
  const placed = (jobs || []).filter((j) => j.preview_receipt);
  const sum = (f) => placed.reduce((a, j) => a + f(j.preview_receipt), 0);
  const base = { l: sum((r) => r.baseline.litres), kg: sum((r) => r.baseline.kg_co2) };
  const sched = { l: sum((r) => r.chosen.litres), kg: sum((r) => r.chosen.kg_co2) };
  return (
    <>
      <h1>Savings</h1>
      <h2>Live jobs</h2>
      {!jobs && !error && <p className="muted">Loading…</p>}
      {placed.length > 0 && <p className="lede">Totals over the {placed.length} placed jobs, compared with running each one
        immediately in the region it was submitted from. Modelled from placement-time forecasts.</p>}
      <ErrorBox error={error} />
      {jobs && placed.length === 0 && <div className="card">No placed jobs yet.</div>}
      {placed.length > 0 && (
        <div className="grid2">
          <Bars title="Water" unit="L" base={base.l} sched={sched.l} format={fmt.litres} />
          <Bars title="Carbon" unit="kg CO₂" base={base.kg} sched={sched.kg} format={fmt.kg} />
        </div>
      )}
      {replay ? <Replay data={replay} /> : <div className="card small muted">No replay yet. Run <code>python scripts/replay.py</code>.</div>}
    </>
  );
}
