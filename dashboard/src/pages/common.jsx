import React from "react";

export function ErrorBox({ error }) {
  if (!error) return null;
  return <div className="error" role="alert"><strong>Something went wrong.</strong> {String(error.message || error)}</div>;
}

/** Where the inputs come from. Warns only when something is genuinely not live; the carbon forecast
 *  holding its last value past its horizon is normal and gets a quiet note. */
export function SourcesBanner({ regions }) {
  const synthetic = regions.filter((r) => r.weather_sources?.includes("synthetic")).map((r) => r.id);
  const modelled = regions.filter((r) => r.ci_sources?.includes("modelled")).map((r) => r.id);
  const held = regions.some((r) => r.ci_sources?.some((s) => s.endsWith("latest-held")));
  return (
    <>
      {synthetic.length > 0 && <div className="banner warn" role="note"><strong>Synthetic weather</strong> for {synthetic.join(", ")}. Offline mode, not a forecast.</div>}
      {modelled.length > 0 && <div className="banner warn" role="note"><strong>Modelled carbon</strong> for {modelled.join(", ")}: no live Electricity Maps forecast.</div>}
      {held && !modelled.length && <p className="small muted">Carbon intensity is Electricity Maps forecast data. Past each forecast's horizon the last value is held.</p>}
    </>
  );
}

export function Status({ value }) {
  return <span className={`tag ${value}`}>{value}</span>;
}

export function PageHead({ eyebrow, title, children }) {
  return (
    <header className="page-head">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {children && <p className="lede">{children}</p>}
    </header>
  );
}

export function Readout({ label, value, unit, children }) {
  return (
    <div className="readout">
      <div className="label">{label}</div>
      <div className="value">{value}{unit && <small>{unit}</small>}</div>
      {children && <div className="delta">{children}</div>}
    </div>
  );
}

export function Loading({ rows = 3 }) {
  return <div className="stack" aria-busy="true" aria-label="Loading">{Array.from({ length: rows }, (_, i) =>
    <div key={i} className="skel" style={{ width: `${90 - i * 14}%` }} />)}</div>;
}

export function Empty({ title, children }) {
  return <div className="empty"><strong>{title}</strong><div>{children}</div></div>;
}
