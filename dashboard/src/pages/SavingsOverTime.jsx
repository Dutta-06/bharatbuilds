import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { ErrorBox } from "./common.jsx";

const H = 220, PAD = { l: 48, r: 12, t: 12, b: 28 };

// One series (cumulative litres saved), so no legend: the card title names it.
function Line({ daily }) {
  const [hover, setHover] = useState(null);
  const [W, setW] = useState(640);          // real pixel width, so text stays 11px on phones
  const svg = useRef(null);
  const box = useRef(null);
  useLayoutEffect(() => {
    const el = box.current;
    const measure = () => setW(Math.max(260, Math.round(el.getBoundingClientRect().width)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const ys = daily.map((d) => d.cumulative_litres_saved);
  const max = Math.max(...ys, 1e-9);
  const x = (i) => PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(1, daily.length - 1);
  const y = (v) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b);
  const path = daily.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.cumulative_litres_saved).toFixed(1)}`).join(" ");
  const ticks = [0, 0.5, 1].map((f) => f * max);
  const move = (e) => {
    const box = svg.current.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    setHover(Math.min(daily.length - 1, Math.max(0, Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (daily.length - 1)))));
  };
  const h = hover != null ? daily[hover] : null;
  return (
    <div ref={box} style={{ position: "relative" }}>
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" onPointerMove={move} onPointerLeave={() => setHover(null)}
        aria-label={`Cumulative litres saved over ${daily.length} days, reaching ${fmt.litres(ys[ys.length - 1])} litres`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
            <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{fmt.litres(t)}</text>
          </g>))}
        {[0, Math.floor((daily.length - 1) / 2), daily.length - 1].map((i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === daily.length - 1 ? "end" : "middle"}
            fontSize="11" fill="var(--muted)">{daily[i].date.slice(5)}</text>))}
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {h && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} stroke="var(--axis)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(h.cumulative_litres_saved)} r="4.5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" />
          </g>)}
      </svg>
      {h && (
        <div className="small" role="status" style={{ position: "absolute", top: 4, width: 150,
          left: Math.max(0, x(hover) > W / 2 ? x(hover) - 160 : x(hover) + 10),
          background: "var(--surface)", border: "1px solid var(--ring)", borderRadius: 6, padding: "4px 8px", pointerEvents: "none" }}>
          <strong>{h.date}</strong><br />{fmt.litres(h.cumulative_litres_saved)} L saved in total<br />
          {h.jobs} job{h.jobs === 1 ? "" : "s"} that day
        </div>)}
    </div>
  );
}

export default function SavingsOverTime() {
  const [team, setTeam] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    setError(null);
    api.savings({ days: 30, ...(team ? { team } : {}) }).then(setData).catch(setError);
  }, [team]);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <p className="muted">Loading…</p>;
  const t = data.totals;
  return (
    <>
      <h2>Savings over time</h2>
      <p className="lede">Last {data.days} days{team ? `, team ${team}` : ", all teams"}. {data.note}</p>
      <div className="grid2">
        <div className="card"><div className="muted small">Water saved</div><div className="hero">{fmt.litres(t.litres_saved)} L</div></div>
        <div className="card"><div className="muted small">Carbon saved</div><div className="hero">{fmt.kg(t.kg_co2_saved)} kg</div></div>
        <div className="card"><div className="muted small">Jobs placed / run</div><div className="hero">{t.jobs} <small>/ {t.done} have run</small></div></div>
      </div>
      {t.jobs === 0 ? <div className="card">No placed jobs in this window{team ? " for this team" : ""}.</div> : (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Cumulative water saved (litres)</h3>
          <Line daily={data.daily} />
          <details>
            <summary className="small">Show as table</summary>
            <div className="scroll"><table>
              <thead><tr><th>Date</th><th className="num">Jobs</th><th className="num">Water saved (L)</th><th className="num">CO₂ saved (kg)</th>
                <th className="num">Cumulative water (L)</th></tr></thead>
              <tbody>{data.daily.filter((d) => d.jobs > 0).map((d) => (
                <tr key={d.date}><td>{d.date}</td><td className="num">{d.jobs}</td><td className="num">{fmt.litres(d.litres_saved)}</td>
                  <td className="num">{fmt.kg(d.kg_co2_saved)}</td><td className="num">{fmt.litres(d.cumulative_litres_saved)}</td></tr>))}</tbody>
            </table></div>
          </details>
        </div>)}
      <div className="card scroll">
        <h3 style={{ marginTop: 0 }}>By team</h3>
        <table>
          <thead><tr><th>Team</th><th className="num">Jobs</th><th className="num">Have run</th><th className="num">Water saved (L)</th><th className="num">CO₂ saved (kg)</th></tr></thead>
          <tbody>{data.by_team.map((r) => (
            <tr key={r.team}><td><a href="#/savings" onClick={() => setTeam(team === r.team ? "" : r.team)}>{r.team}</a></td>
              <td className="num">{r.jobs}</td><td className="num">{r.done}</td>
              <td className="num">{fmt.litres(r.litres_saved)}</td><td className="num">{fmt.kg(r.kg_co2_saved)}</td></tr>))}</tbody>
        </table>
        <p className="small muted">Select a team to filter; select it again to clear. Jobs submitted without a team count as "unassigned".</p>
      </div>
    </>
  );
}
