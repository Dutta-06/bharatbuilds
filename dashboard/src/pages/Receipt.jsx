import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../colors.js";
import { download, receiptRows, toCsv } from "../exportReceipt.js";
import { ErrorBox, Loading, PageHead, Readout } from "./common.jsx";

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
  if (!data) return <Loading rows={5} />;
  const { job, receipt } = data;
  const rows = receiptRows(job, receipt);
  const copy = async () => {
    try { await navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { window.prompt("Copy this link", window.location.href); }
  };
  const view = receipt?.declared_job?.receipt || job.preview_receipt;
  return (
    <>
      <PageHead eyebrow={<>Receipt <span className="num">{job.job_id}</span></>} title={job.name || "Job receipt"}>
        {job.request.gpu_hours} GPU-hours{receipt ? <>, ran in <b className="num">{receipt.ran_in}</b></> : ", not yet run. This is the modelled preview, not a final receipt"}.
      </PageHead>
      {view && (
        <div className="readouts">
          <Readout label="Water" value={fmt.litres(view.chosen.litres)} unit="L">against {fmt.litres(view.baseline.litres)} L running now · {view.saved.litres_pct?.toFixed(0)}% saved</Readout>
          <Readout label="Carbon" value={fmt.kg(view.chosen.kg_co2)} unit="kg CO₂">against {fmt.kg(view.baseline.kg_co2)} kg running now · {view.saved.kg_co2_pct?.toFixed(0)}% saved</Readout>
        </div>
      )}
      <div className="panel"><dl className="kv">{rows.filter(([, v]) => v !== "" && v != null).map(([k, v]) => (<React.Fragment key={k}><dt>{k}</dt><dd>{String(v ?? "")}</dd></React.Fragment>))}</dl></div>
      <div className="actions no-print">
        <button className="primary" onClick={copy}>{copied ? "Link copied" : "Copy link"}</button>
        <button className="btn" onClick={() => download(`pravaah-receipt-${job.job_id}.json`, JSON.stringify({ job, receipt }, null, 2), "application/json")}>Download JSON</button>
        <button className="btn" onClick={() => download(`pravaah-receipt-${job.job_id}.csv`, toCsv(rows), "text/csv")}>Download CSV</button>
        <button className="btn" onClick={() => window.print()}>Print or save as PDF</button>
      </div>
      <p className="small muted" style={{ maxWidth: "70ch" }}>Savings compare running the job immediately in its comparison region. Water and carbon are modelled from forecast
        weather and grid data, with ranges. Only the energy of the stand-in CPU workload is measured.</p>
    </>
  );
}
