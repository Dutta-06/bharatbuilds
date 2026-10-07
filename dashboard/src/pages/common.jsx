import React from "react";

export function ErrorBox({ error }) {
  if (!error) return null;
  return <div className="card error" role="alert"><strong>Something went wrong.</strong> {String(error.message || error)}</div>;
}

export function SourcesBanner({ regions }) {
  const synthetic = regions.filter((r) => r.weather_sources?.includes("synthetic")).map((r) => r.id);
  const modelled = regions.filter((r) => r.ci_sources?.some((s) => s === "modelled" || s.endsWith("latest-held"))).map((r) => r.id);
  if (!synthetic.length && !modelled.length) return null;
  return (
    <div className="banner" role="note">
      {synthetic.length > 0 && <div><strong>Synthetic weather</strong> (offline mode) for {synthetic.join(", ")}. Not a forecast.</div>}
      {modelled.length > 0 && <div><strong>Modelled carbon</strong> (no live Electricity Maps forecast) for {modelled.join(", ")}.</div>}
    </div>
  );
}

export function Status({ value }) {
  return <span className={`status ${value}`}>{value}</span>;
}
