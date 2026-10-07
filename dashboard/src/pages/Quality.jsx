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
      <p className="lede">Where each input comes from right now. Forecast error (MAE against what actually happened)
        appears here once the Step 4 models are trained and scored against persistence and the provider forecast.</p>
      <ErrorBox error={error} />
      <div className="card scroll">
        <table>
          <thead><tr><th>Region</th><th>Weather</th><th>Carbon</th><th>Cooling model</th><th>Calibrated to disclosed WUE</th>
            <th className="num">Water-stress ×</th></tr></thead>
          <tbody>
            {regions.map((r) => {
              const s = data?.regions.find((x) => x.id === r.id);
              return (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{s ? s.weather_sources.join(", ") : <span className="muted">no data</span>}</td>
                  <td>{s ? s.ci_sources.join(", ") : <span className="muted">no data</span>}</td>
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
