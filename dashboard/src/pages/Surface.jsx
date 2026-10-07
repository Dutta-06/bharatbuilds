import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { api } from "../api.js";
import { costColor, fmt, isDark } from "../colors.js";
import { ErrorBox, SourcesBanner } from "./common.jsx";

export default function Surface() {
  const [gpuHours, setGpuHours] = useState(4);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setError(null);
    api.surface({ gpu_hours: gpuHours }).then((d) => { setData(d); setIdx(0); }).catch(setError);
  }, [gpuHours]);

  const hour = data?.hours?.[idx];
  const rows = useMemo(() => {
    if (!data) return [];
    return data.regions
      .map((r) => ({ ...r, cell: r.cells.find((c) => c.hour === hour) }))
      .filter((r) => r.cell)
      .sort((a, b) => a.cell.cost - b.cell.cost);
  }, [data, hour]);
  const [lo, hi] = useMemo(() => {
    const all = data ? data.regions.flatMap((r) => r.cells.map((c) => c.cost)) : [1];
    return [Math.min(...all), Math.max(...all)];
  }, [data]);

  return (
    <>
      <h1>Cost surface</h1>
      <p className="lede">The water and carbon price of running {gpuHours} GPU-hours in each region, hour by hour,
        for the next 48 hours. 1.00 means the same as running now in {data?.baseline?.region || "the baseline region"};
        lower is better.</p>
      <ErrorBox error={error} />
      {data && <SourcesBanner regions={data.regions} />}
      <div className="card">
        <div className="grid2">
          <label>GPU-hours
            <input type="number" min="0.25" step="0.25" value={gpuHours}
                   onChange={(e) => setGpuHours(Math.max(0.25, Number(e.target.value) || 1))} />
          </label>
          <label>Hour: <strong>{fmt.hour(hour)}</strong>
            <input type="range" min="0" max={Math.max(0, (data?.hours?.length || 1) - 1)} value={idx}
                   onChange={(e) => setIdx(Number(e.target.value))} aria-label="Hour of the forecast" />
          </label>
        </div>
        <CostMap rows={rows} lo={lo} hi={hi} />
        <div className="legend" aria-hidden="true">
          <span>cheaper</span>
          <span className="ramp" style={{ background: `linear-gradient(90deg, ${costColor(lo, lo, hi)}, ${costColor(1, lo, hi)}, ${costColor(hi, lo, hi)})` }} />
          <span>costlier than running now in {data?.baseline?.region}</span>
        </div>
      </div>
      {data?.best && (
        <div className="card"><span className="muted">Cheapest slot in the next 48 h:</span>{" "}
          <strong>{data.best.region}</strong> at {fmt.hour(data.best.hour)} (cost {data.best.cost.toFixed(2)})</div>
      )}
      <div className="card scroll">
        <h2 style={{ marginTop: 0 }}>At {fmt.hour(hour)}</h2>
        <table>
          <thead><tr><th>Region</th><th className="num">Cost</th><th className="num">Water (L)</th>
            <th className="num">CO₂ (kg)</th><th className="num">Wet-bulb °C</th><th className="num">gCO₂/kWh</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="region"><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, marginRight: 6,
                  background: costColor(r.cell.cost, lo, hi), border: "1px solid var(--ring)" }} />{r.id} <span className="muted small hide-sm">{r.name}</span></td>
                <td className="num">{r.cell.cost.toFixed(2)}</td>
                <td className="num" title={`${fmt.litres(r.cell.litres_low)} – ${fmt.litres(r.cell.litres_high)}`}>{fmt.litres(r.cell.litres)}</td>
                <td className="num" title={`${fmt.kg(r.cell.kg_low)} – ${fmt.kg(r.cell.kg_high)}`}>{fmt.kg(r.cell.kg_co2)}</td>
                <td className="num">{r.cell.t_wb}</td>
                <td className="num">{r.cell.ci == null ? "–" : Math.round(r.cell.ci)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small muted">Hover a value for its uncertainty range. Water = on-site cooling + power-plant water.</p>
      </div>
    </>
  );
}

function CostMap({ rows, lo, hi }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);
  useEffect(() => {
    map.current = L.map(el.current, { worldCopyJump: true, scrollWheelZoom: false }).setView([25, 40], 2);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 6, attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => map.current.remove();
  }, []);
  useEffect(() => {
    layer.current.clearLayers();
    // A muted outline keeps markers near the neutral midpoint visible over map tiles.
    const outline = isDark() ? "#c3c2b7" : "#52514e";
    rows.forEach((r) => {
      L.circleMarker([r.lat, r.lon], {
        radius: 11, color: outline, weight: 1.5, fillColor: costColor(r.cell.cost, lo, hi), fillOpacity: 1,
      }).bindTooltip(
        `<strong>${r.id}</strong><br>cost ${r.cell.cost.toFixed(2)}<br>${fmt.litres(r.cell.litres)} L water · ${fmt.kg(r.cell.kg_co2)} kg CO₂<br>wet-bulb ${r.cell.t_wb} °C`,
        { direction: "top" },
      ).addTo(layer.current);
    });
  }, [rows, lo, hi]);
  return <div className="map" ref={el} role="img" aria-label="Map of regions coloured by cost; the table below has the same data" />;
}
