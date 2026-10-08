import React, { useEffect, useState } from "react";
import { fmt } from "../colors.js";
import { PageHead, Readout } from "./common.jsx";
import SavingsOverTime from "./SavingsOverTime.jsx";

function Bars({ title, unit, base, sched, format }) {
  const max = Math.max(base, sched, 1e-9);
  return (
    <div className="panel stack" style={{ gap: 12 }}>
      <div className="section-title" style={{ margin: 0 }}>{title}</div>
      <div className="bars" role="table" aria-label={title}>
        {[["Run now, here", base, "var(--line-strong)"], ["Pravaah", sched, "var(--ink)"]].map(([label, v, color]) => (
          <div className="bar-row" role="row" key={label}>
            <span role="cell">{label}</span>
            <div className="bar-track" role="cell"><div className="bar" style={{ width: `${(100 * v) / max}%`, background: color }} /></div>
            <span role="cell">{format(v)} {unit}</span>
          </div>
        ))}
      </div>
      {base > 0 && <p className="small"><b>{(100 * (base - sched) / base).toFixed(0)}% less</b> with Pravaah.</p>}
    </div>
  );
}

function Replay({ data }) {
  const h = data.headline;
  const ww = data.when_vs_where;
  return (
    <section className="stack" style={{ gap: 20 }}>
      <div className="rule-top">
        <div className="section-title">Trace replay · {h.jobs} jobs</div>
        <p className="lede">The same queue run two ways: every job started immediately where it was submitted, and placed by Pravaah.</p>
      </div>
      <div className="banner warn small" role="note">
        <strong>Read these with their assumptions.</strong>
        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{data.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </div>
      <div className="cols">
        <Bars title="Water, whole queue" unit="L" base={h.naive.litres} sched={h.pravaah.litres} format={fmt.litres} />
        <Bars title="Carbon, whole queue" unit="kg CO₂" base={h.naive.kg_co2} sched={h.pravaah.kg_co2} format={fmt.kg} />
      </div>
      <div className="readouts">
        <Readout label="Deadlines met" value={h.deadline_hit_rate_pct} unit="%" />
        <Readout label="Median delay" value={h.median_delay_h} unit="h" />
        <Readout label="Moved region" value={h.moved_region_pct} unit="% of jobs" />
      </div>
      <div>
        <div className="section-title">When versus where</div>
        <div className="panel tight scroll"><table>
          <thead><tr><th>Scenario</th><th className="num">Water saved</th><th className="num">CO₂ saved</th><th className="num">Median delay</th></tr></thead>
          <tbody>
            <tr><td>Shift time only, stay in the submit region</td><td className="num">{ww.time_only_same_region.saved_pct.litres}%</td>
              <td className="num">{ww.time_only_same_region.saved_pct.kg_co2}%</td><td className="num">{ww.time_only_same_region.median_delay_h} h</td></tr>
            <tr><td>Shift time and region (Pravaah)</td><td className="num">{ww.time_and_region.saved_pct.litres}%</td>
              <td className="num">{ww.time_and_region.saved_pct.kg_co2}%</td><td className="num">{ww.time_and_region.median_delay_h} h</td></tr>
          </tbody>
        </table></div>
      </div>
      <div className="cols">
        <div>
          <div className="section-title">Deadline slack</div>
          <div className="panel tight scroll"><table>
            <thead><tr><th>Slack beyond job length</th><th className="num">Water</th><th className="num">CO₂</th></tr></thead>
            <tbody>{data.slack_sensitivity.map((r) => (
              <tr key={r.extra_slack_h}><td className="mono">+{r.extra_slack_h} h</td><td className="num">{r.saved_pct.litres}%</td><td className="num">{r.saved_pct.kg_co2}%</td></tr>))}</tbody>
          </table></div>
        </div>
        <div>
          <div className="section-title">Optimising for</div>
          <div className="panel tight scroll"><table>
            <thead><tr><th>Weights</th><th className="num">Water</th><th className="num">CO₂</th></tr></thead>
            <tbody>{data.weight_sensitivity.map((r) => (
              <tr key={r.weights}><td>{r.weights}</td><td className="num">{r.saved_pct.litres}%</td><td className="num">{r.saved_pct.kg_co2}%</td></tr>))}</tbody>
          </table></div>
        </div>
      </div>
    </section>
  );
}

export default function Savings() {
  const [replay, setReplay] = useState(null);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}replay.json`).then((r) => (r.ok ? r.json() : null)).then(setReplay).catch(() => setReplay(null));
  }, []);
  return (
    <>
      <PageHead eyebrow="Modelled, not metered" title="Savings">
        What placement has saved compared with running each job right away in the region it was submitted from.
      </PageHead>
      <SavingsOverTime />
      {replay ? <Replay data={replay} /> : <p className="small muted rule-top">No replay yet. Run <code>python scripts/replay.py</code>.</p>}
    </>
  );
}
