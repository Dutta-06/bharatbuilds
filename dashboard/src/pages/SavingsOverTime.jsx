import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { Empty, ErrorBox, Loading, Readout } from "./common.jsx";

const H = 220, PAD = { l: 48, r: 12, t: 12, b: 28 };

// One series (cumulative litres saved), so no legend: the heading names it.
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
  const area = `${path} L${x(daily.length - 1).toFixed(1)},${y(0)} L${x(0).toFixed(1)},${y(0)} Z`;
  const ticks = [0, 0.5, 1].map((f) => f * max);
  const move = (e) => {
    const b = svg.current.getBoundingClientRect();
    const px = ((e.clientX - b.left) / b.width) * W;
    setHover(Math.min(daily.length - 1, Math.max(0, Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (daily.length - 1)))));
  };
  const h = hover != null ? daily[hover] : null;
  return (
    <div ref={box} style={{ position: "relative" }}>
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" onPointerMove={move} onPointerLeave={() => setHover(null)}
        aria-label={`Cumulative litres saved over ${daily.length} days, reaching ${fmt.litres(ys[ys.length - 1])} litres`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth="1" />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fontFamily="var(--font-mono)" fill="var(--muted)">{fmt.litres(t)}</text>
          </g>))}
        {[0, Math.floor((daily.length - 1) / 2), daily.length - 1].map((i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === daily.length - 1 ? "end" : "middle"}
            fontSize="11" fontFamily="var(--font-mono)" fill="var(--muted)">{daily[i].date.slice(5)}</text>))}
        <path d={area} fill="var(--ink)" opacity="0.06" />
        <path d={path} fill="none" stroke="var(--ink)" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(daily.length - 1)} cy={y(ys[ys.length - 1])} r="3.5" fill="var(--ink)" stroke="var(--panel)" strokeWidth="2" />
        {h && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} stroke="var(--line-strong)" strokeWidth="1" />
            <circle cx={x(hover)} cy={y(h.cumulative_litres_saved)} r="4.5" fill="var(--ink)" stroke="var(--panel)" strokeWidth="2" />
          </g>)}
      </svg>
      {h && (
        <div className="tip" role="status" style={{ position: "absolute", top: 4, width: 156, pointerEvents: "none",
          left: Math.max(0, x(hover) > W / 2 ? x(hover) - 166 : x(hover) + 10) }}>
          <b>{h.date}</b><br />{fmt.litres(h.cumulative_litres_saved)} L saved in total<br />{h.jobs} job{h.jobs === 1 ? "" : "s"} that day
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
  if (!data) return <Loading rows={4} />;
  const t = data.totals;
  return (
    <section className="stack" style={{ gap: 20 }}>
      <div className="section-title" style={{ margin: 0 }}>Last {data.days} days · {team ? `team ${team}` : "all teams"}</div>
      <div className="readouts">
        <Readout label="Water saved" value={fmt.litres(t.litres_saved)} unit="L" />
        <Readout label="Carbon saved" value={fmt.kg(t.kg_co2_saved)} unit="kg CO₂" />
        <Readout label="Jobs placed" value={t.jobs} unit={`${t.done} have run`} />
      </div>
      {t.jobs === 0 ? <Empty title="No placed jobs in this window">{team ? "Clear the team filter to see all jobs." : <a className="btn primary" href="#/submit">Submit a job</a>}</Empty> : (
        <div className="panel stack" style={{ gap: 10 }}>
          <h2>Cumulative water saved, litres</h2>
          <Line daily={data.daily} />
          <details>
            <summary className="small" style={{ cursor: "pointer" }}>Show as table</summary>
            <div className="scroll"><table>
              <thead><tr><th>Date</th><th className="num">Jobs</th><th className="num">Water saved L</th><th className="num">CO₂ saved kg</th><th className="num">Cumulative L</th></tr></thead>
              <tbody>{data.daily.filter((d) => d.jobs > 0).map((d) => (
                <tr key={d.date}><td className="num">{d.date}</td><td className="num">{d.jobs}</td><td className="num">{fmt.litres(d.litres_saved)}</td>
                  <td className="num">{fmt.kg(d.kg_co2_saved)}</td><td className="num">{fmt.litres(d.cumulative_litres_saved)}</td></tr>))}</tbody>
            </table></div>
          </details>
        </div>)}
      <div>
        <div className="section-title">By team</div>
        <div className="panel tight scroll"><table>
          <thead><tr><th>Team</th><th className="num">Jobs</th><th className="num">Have run</th><th className="num">Water saved L</th><th className="num">CO₂ saved kg</th></tr></thead>
          <tbody>{data.by_team.map((r) => (
            <tr key={r.team}><td><button type="button" className="chip" aria-pressed={team === r.team} onClick={() => setTeam(team === r.team ? "" : r.team)}>{r.team}</button></td>
              <td className="num">{r.jobs}</td><td className="num">{r.done}</td><td className="num">{fmt.litres(r.litres_saved)}</td><td className="num">{fmt.kg(r.kg_co2_saved)}</td></tr>))}</tbody>
        </table></div>
        <p className="small muted" style={{ marginTop: 8 }}>Select a team to filter. Jobs submitted without a team count as unassigned. Figures are modelled from each job's placement.</p>
      </div>
    </section>
  );
}
