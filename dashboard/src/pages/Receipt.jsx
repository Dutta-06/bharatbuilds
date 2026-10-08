import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { download, receiptRows, toCsv } from "../exportReceipt.js";
import { ErrorBox } from "./common.jsx";

// Shareable, printable receipt: #/receipt/<job id>. Same data as the job page, nothing else.
export default function Receipt({ id }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    (async () => {
      try {
        const job = await api.job(id);
        const r = await api.receipt(id);
        setData({ job, receipt: r.status === 200 ? r.body : null });
      } catch (e) { setError(e); }
    })();
  }, [id]);

  if (error) return <ErrorBox error={error} />;
  if (!data) return <p className="muted">Loading…</p>;
  const { job, receipt } = data;
  const rows = receiptRows(job, receipt);
  const copy = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { window.prompt("Copy this link", window.location.href); }
  };
  const view = receipt?.declared_job?.receipt || job.preview_receipt;
  return (
    <>
      <h1>Receipt {job.job_id}</h1>
      <p className="lede">
        {job.request.gpu_hours} GPU-hours{receipt ? <>, ran in <strong>{receipt.ran_in}</strong></> : ", not yet run"}.{" "}
        {!receipt && <strong>Modelled preview, not a final receipt.</strong>}
      </p>
      {view && (
        <div className="grid2">
          <div className="card"><div className="muted small">Water</div>
            <div className="hero">{fmt.litres(view.chosen.litres)} L <small>vs {fmt.litres(view.baseline.litres)} L</small></div>
            <div className="small">{view.saved.litres_pct?.toFixed(0)}% saved</div></div>
          <div className="card"><div className="muted small">Carbon</div>
            <div className="hero">{fmt.kg(view.chosen.kg_co2)} kg <small>vs {fmt.kg(view.baseline.kg_co2)} kg</small></div>
            <div className="small">{view.saved.kg_co2_pct?.toFixed(0)}% saved</div></div>
        </div>
      )}
      <div className="card scroll">
        <table><tbody>{rows.map(([k, v]) => (
          <tr key={k}><th style={{ textAlign: "left", whiteSpace: "nowrap" }}>{k}</th><td className="small">{String(v ?? "")}</td></tr>))}
        </tbody></table>
      </div>
      <div className="actions no-print">
        <button className="primary" onClick={copy}>{copied ? "Link copied" : "Copy link"}</button>{" "}
        <button className="primary" onClick={() => download(`pravaah-receipt-${job.job_id}.json`,
          JSON.stringify({ job, receipt }, null, 2), "application/json")}>Download JSON</button>{" "}
        <button className="primary" onClick={() => download(`pravaah-receipt-${job.job_id}.csv`, toCsv(rows), "text/csv")}>Download CSV</button>{" "}
        <button className="primary" onClick={() => window.print()}>Print / save as PDF</button>
      </div>
      <p className="small muted">Savings compare running the job immediately in its submit region. Water and carbon
        are modelled from forecast weather and grid data (ranges shown); only the energy of the stand-in CPU workload is measured.</p>
    </>
  );
}
