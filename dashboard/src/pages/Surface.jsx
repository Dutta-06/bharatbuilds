import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { api } from "../api.js";
import { costColor, cssVar, fmt } from "../colors.js";
import { useThemeTick } from "../theme.js";
import { parse, utc, when, whenShort } from "../time.js";
import { ErrorBox, Loading, PageHead, SourcesBanner } from "./common.jsx";

export default function Surface() {
  const tick = useThemeTick();
  const [gpuHours, setGpuHours] = useState(4);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setError(null);
    api.surface({ gpu_hours: gpuHours }).then((d) => { setData(d); setIdx(0); }).catch(setError);
  }, [gpuHours]);

  const hour = data?.hours?.[idx];
  const [lo, hi] = useMemo(() => {
    const all = data ? data.regions.flatMap((r) => r.cells.map((c) => c.cost)) : [1];
    return [Math.min(...all), Math.max(...all)];
  }, [data]);
  // Cheapest regions first, so the eye lands on where to run.
  const ordered = useMemo(() => (data ? [...data.regions].sort((a, b) =>
    Math.min(...a.cells.map((c) => c.cost)) - Math.min(...b.cells.map((c) => c.cost))) : []), [data]);
  const rows = useMemo(() => ordered.map((r) => ({ ...r, cell: r.cells.find((c) => c.hour === hour) }))
    .filter((r) => r.cell).sort((a, b) => a.cell.cost - b.cell.cost), [ordered, hour]);

  return (
    <>
      <PageHead eyebrow="Next 48 hours" title="Cost surface">
        What running {gpuHours} GPU-hours would cost in each region, hour by hour. 1.00 is the same as running now in{" "}
        {data?.baseline?.region || "the comparison region"}; lower is better. Select any hour to see the detail.
      </PageHead>
      <ErrorBox error={error} />
      {data && <SourcesBanner regions={data.regions} />}
      {!data && !error && <Loading rows={4} />}
      {data && (
        <>
          <section className="stack" aria-label="Cost by region and hour">
            <div className="surface-controls">
              <div className="field" style={{ width: 120 }}><label className="lbl" htmlFor="gh">GPU-hours</label>
                <input id="gh" type="number" min="0.25" step="0.25" value={gpuHours}
                  onChange={(e) => setGpuHours(Math.max(0.25, Number(e.target.value) || 1))} /></div>
              <div className="field">
                <label className="lbl" htmlFor="hr">Hour: <span className="num">{when(hour)}</span></label>
                <input id="hr" type="range" min="0" max={Math.max(0, data.hours.length - 1)} value={idx}
                  onChange={(e) => setIdx(Number(e.target.value))} aria-valuetext={`${when(hour)}, ${utc(hour)}`} />
              </div>
              {data.best && (
                <div className="small best-note">
                  <span className="muted">Cheapest slot</span> <b className="num">{data.best.region}</b>{" "}
                  <span className="num">{whenShort(data.best.hour)}</span> <span className="muted">· cost</span> <b className="num">{data.best.cost.toFixed(2)}</b>
                </div>)}
            </div>
            <p className="small muted only-sm">Scroll sideways to see later hours. Tap a column to select it.</p>
            <Heat ordered={ordered} hours={data.hours} idx={idx} setIdx={setIdx} lo={lo} hi={hi} best={data.best} tick={tick} />
            <div className="legend" aria-hidden="true">
              <span>cheaper</span>
              <span className="ramp" style={{ background: `linear-gradient(90deg, ${costColor(lo, lo, hi)}, ${costColor(1, lo, hi)}, ${costColor(hi, lo, hi)})` }} />
              <span>costlier than now in {data.baseline?.region}</span>
              <span style={{ marginLeft: "auto" }}>outlined cell: cheapest slot</span>
            </div>
          </section>

          <section className="surface-detail">
            <div className="stack" style={{ gap: 10 }}>
              <div className="section-title" style={{ margin: 0 }}>At {when(hour)} <span className="muted">({utc(hour)})</span></div>
              <div className="panel tight scroll">
                <table>
                  <thead><tr><th>Region</th><th className="num">Cost</th><th className="num">Water L</th>
                    <th className="num">CO₂ kg</th><th className="num hide-sm">Wet-bulb °C</th><th className="num hide-sm">gCO₂/kWh</th></tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id}>
                        <td className="region"><span className="swatch" style={{ background: costColor(r.cell.cost, lo, hi) }} /><span className="num">{r.id}</span> <span className="muted small hide-sm">{r.name.replace(/^.*\((.*)\)$/, "$1")}</span></td>
                        <td className="num">{r.cell.cost.toFixed(2)}</td>
                        <td className="num" title={`range ${fmt.litres(r.cell.litres_low)} to ${fmt.litres(r.cell.litres_high)} L`}>{fmt.litres(r.cell.litres)}</td>
                        <td className="num" title={`range ${fmt.kg(r.cell.kg_low)} to ${fmt.kg(r.cell.kg_high)} kg`}>{fmt.kg(r.cell.kg_co2)}</td>
                        <td className="num hide-sm">{r.cell.t_wb}</td>
                        <td className="num hide-sm">{r.cell.ci == null ? "–" : Math.round(r.cell.ci)}</td>
                      </tr>))}
                  </tbody>
                </table>
              </div>
              <p className="small muted">Hover a water or carbon value for its uncertainty range. Water is on-site cooling plus power-plant water.</p>
            </div>
            <div className="stack" style={{ gap: 10 }}>
              <div className="section-title" style={{ margin: 0 }}>Regions at this hour</div>
              <CostMap rows={rows} lo={lo} hi={hi} tick={tick} />
            </div>
          </section>
        </>
      )}
    </>
  );
}

/** Region × hour grid: the surface itself. Cells are mouse targets; the hour slider is the keyboard route. */
function Heat({ ordered, hours, idx, setIdx, lo, hi, best, tick }) {
  const cols = hours.length;
  return (
    <div className="scroll" style={{ paddingBottom: 6 }}>
      <div className="heat" style={{ "--cols": cols }} role="img"
        aria-label={`Cost for ${ordered.length} regions over ${cols} hours. The table below gives the same figures for the selected hour.`}>
        <div className="heat-axis" aria-hidden="true">
          <span />
          {hours.map((h) => {
            const d = parse(h); const hh = d.getHours();
            return <span key={h}>{hh % 6 === 0 ? (hh === 0 ? whenShort(h).split(" ")[0] : String(hh).padStart(2, "0")) : ""}</span>;
          })}
        </div>
        {ordered.map((r) => (
          <div className="heat-row" key={r.id} style={{ "--cols": cols }}>
            <span className="rid">{r.id}</span>
            {hours.map((h, i) => {
              const c = r.cells.find((x) => x.hour === h);
              if (!c) return <span key={h} />;
              const isBest = best && best.region === r.id && best.hour === h;
              return (
                <button key={h} type="button" tabIndex={-1} onClick={() => setIdx(i)}
                  className={`heat-cell${i === idx ? " pick" : ""}${isBest ? " best" : ""}`}
                  style={{ background: costColor(c.cost, lo, hi) }}
                  title={`${r.id}, ${when(h)}: cost ${c.cost.toFixed(2)}, ${fmt.litres(c.litres)} L, ${fmt.kg(c.kg_co2)} kg CO₂`}
                  aria-label={`${r.id} ${when(h)} cost ${c.cost.toFixed(2)}`} />
              );
            })}
          </div>))}
      </div>
    </div>
  );
}

function CostMap({ rows, lo, hi, tick }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);
  const tiles = useRef(null);
  useEffect(() => {
    map.current = L.map(el.current, { maxBounds: [[-60, -180], [85, 180]], minZoom: 1, scrollWheelZoom: false, zoomControl: true, attributionControl: false }).setView([30, 30], 1);
    layer.current = L.layerGroup().addTo(map.current);
    return () => map.current.remove();
  }, []);
  useEffect(() => {
    // No tile service: land is a bundled public-domain outline (Natural Earth), drawn in theme colours,
    // so the map needs no API key or network and the only colour on it is the cost.
    let alive = true;
    import("../land.json").then(({ default: land }) => {
      if (!alive || !map.current) return;
      tiles.current?.remove();
      tiles.current = L.geoJSON(land, { interactive: false, style: { color: cssVar("--line-strong"), weight: 0.8, fillColor: cssVar("--panel-2"), fillOpacity: 1 } }).addTo(map.current);
      tiles.current.bringToBack();
    });
    return () => { alive = false; };
  }, [tick]);
  useEffect(() => {
    layer.current.clearLayers();
    const outline = cssVar("--ink");
    rows.forEach((r) => {
      L.circleMarker([r.lat, r.lon], { radius: 9, color: outline, weight: 1.25, fillColor: costColor(r.cell.cost, lo, hi), fillOpacity: 1 })
        .bindTooltip(`<b>${r.id}</b><br>cost ${r.cell.cost.toFixed(2)}<br>${fmt.litres(r.cell.litres)} L · ${fmt.kg(r.cell.kg_co2)} kg CO₂`, { direction: "top" })
        .addTo(layer.current);
    });
  }, [rows, lo, hi, tick]);
  return <div className="map" ref={el} role="img" aria-label="Map of regions coloured by cost; the table has the same figures" />;
}
