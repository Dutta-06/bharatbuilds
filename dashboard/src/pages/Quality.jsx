import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorBox, Loading, PageHead } from "./common.jsx";

const NAMES = { "open-meteo": "Open-Meteo", "synthetic": "synthetic (offline)", "modelled": "modelled profile",
  "electricitymaps-forecast": "Electricity Maps forecast", "electricitymaps-latest-held": "last value held", "electricitymaps": "Electricity Maps" };
const label = (s) => NAMES[s] || s;

export default function Quality() {
  const [data, setData] = useState(null);
  const [regions, setRegions] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.surface({ gpu_hours: 1 }).then(setData).catch(setError);
    api.regions().then(setRegions).catch(setError);
  }, []);
  const none = <span className="muted">–</span>;
  return (
    <>
      <PageHead title="Forecasts">
        Where each input comes from and how wrong the last run was. A trained model replaces the provider's forecast only
        where it beat both the provider and persistence (repeating yesterday) on a held-out week.
      </PageHead>
      <ErrorBox error={error} />
      {!regions.length && !error && <Loading rows={4} />}
      {regions.length > 0 && (
        <>
          <div className="panel tight scroll">
            <table>
              <thead><tr><th>Region</th><th>Weather</th><th>Wet-bulb from</th><th>Carbon from</th>
                <th className="num">Wet-bulb error °C</th><th className="num">Carbon error g/kWh</th><th>Cooling</th><th className="num">Stress ×</th></tr></thead>
              <tbody>
                {regions.map((r) => {
                  const s = data?.regions.find((x) => x.id === r.id);
                  const model = s?.t_wb_sources?.includes("model");
                  return (
                    <tr key={r.id}>
                      <td className="mono">{r.id}</td>
                      <td>{s ? s.weather_sources.map(label).join(", ") : none}</td>
                      <td>{s?.t_wb_sources?.length ? <span className="tag" style={{ borderColor: model ? "var(--ink)" : undefined }}>{model ? "trained model" : "provider"}</span> : none}</td>
                      <td className="small">{s ? s.ci_sources.map(label).join(", ") : none}</td>
                      <td className="num">{s?.forecast_error ? s.forecast_error.mae_t_wb.toFixed(2) : "–"}</td>
                      <td className="num">{s?.forecast_error ? s.forecast_error.mae_ci.toFixed(0) : "–"}</td>
                      <td>{r.cooling_type}</td>
                      <td className="num">{r.water_stress_multiplier.toFixed(2)}</td>
                    </tr>);
                })}
              </tbody>
            </table>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            <p className="small muted" style={{ maxWidth: "74ch" }}>Error is the previous run's prediction against this run's first three hours, a stand-in for observations.
              Stress × is the water-stress multiplier from WRI Aqueduct; 1.00 means no score has been entered yet.</p>
            {regions.some((r) => !r.calibrated) && <p className="small muted" style={{ maxWidth: "74ch" }}>Cooling-water curves are not yet calibrated to AWS's disclosed figures for {regions.every((r) => !r.calibrated) ? "any region" : regions.filter((r) => !r.calibrated).map((r) => r.id).join(", ")}, so absolute litres are less certain than the ranking between hours.</p>}
          </div>
        </>
      )}
    </>
  );
}
