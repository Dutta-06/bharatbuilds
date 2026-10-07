import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { ErrorBox } from "./common.jsx";

export default function Quality() {
  const [data, setData] = useState(null);
  const [regions, setRegions] = useState([]);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.surface({ gpu_hours: 1 }).then(setData).catch(setError);
    api.regions().then(setRegions).catch(setError);
  }, []);
  return (
    <>
      <h1>Forecast quality</h1>
      <p className="lede">Where each input comes from, and how wrong the last forecast was. Error is the previous run's
        prediction against this run's first 3 hours (a nowcast proxy for observations). A trained model replaces the
        provider forecast only where it beat both persistence and the provider on held-out days.</p>
      <ErrorBox error={error} />
      <div className="card scroll">
        <table>
          <thead><tr><th>Region</th><th>Weather</th><th>Wet-bulb</th><th>Carbon</th>
            <th className="num">Last error, wet-bulb °C</th><th className="num">Last error, gCO₂/kWh</th>
            <th>Cooling</th><th>Calibrated</th><th className="num">Stress ×</th></tr></thead>
          <tbody>
            {regions.map((r) => {
              const s = data?.regions.find((x) => x.id === r.id);
              return (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{s ? s.weather_sources.join(", ") : <span className="muted">no data</span>}</td>
                  <td>{s?.t_wb_sources?.length ? s.t_wb_sources.join(", ") : <span className="muted">–</span>}</td>
                  <td>{s ? s.ci_sources.join(", ") : <span className="muted">no data</span>}</td>
                  <td className="num">{s?.forecast_error ? s.forecast_error.mae_t_wb.toFixed(2) : "–"}</td>
                  <td className="num">{s?.forecast_error ? s.forecast_error.mae_ci.toFixed(0) : "–"}</td>
                  <td>{r.cooling_type}</td>
                  <td>{r.calibrated ? "yes" : <span style={{ color: "var(--bad)" }}>not yet</span>}</td>
                  <td className="num">{r.water_stress_multiplier.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
