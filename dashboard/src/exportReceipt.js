// Flat, human-readable rows for a receipt, shared by the CSV export and the printable page.
// Takes the job (GET /jobs/{id}) and the final receipt (GET /jobs/{id}/receipt, or null).
export function receiptRows(job, receipt) {
  const view = receipt?.declared_job?.receipt || job.preview_receipt;
  const rows = [
    ["Job", job.job_id], ["Name", job.name || ""], ["Team", job.team || ""], ["Status", job.status],
    ["Submitted (UTC)", job.submitted_at], ["Deadline (UTC)", job.request.deadline],
    ["GPU-hours", job.request.gpu_hours], ["GPU", job.request.gpu],
    ["Final receipt", receipt ? "yes (job has run)" : "no (modelled preview from placement time)"],
  ];
  if (receipt) {
    rows.push(["Ran in", receipt.ran_in], ["Requested region", receipt.requested_region],
      ["Launched via", receipt.launched_via],
      ["Proxy workload", receipt.proxy_run?.what], ["Measured CPU energy (kWh)", receipt.proxy_run?.energy_kwh]);
  }
  if (view) {
    const { chosen, baseline, saved } = view;
    rows.push(
      ["Water, chosen (L)", chosen.litres], ["Water range (L)", `${chosen.litres_low} to ${chosen.litres_high}`],
      ["Water, run now here (L)", baseline.litres], ["Water saved (%)", saved.litres_pct],
      ["CO2, chosen (kg)", chosen.kg_co2], ["CO2 range (kg)", `${chosen.kg_low} to ${chosen.kg_high}`],
      ["CO2, run now here (kg)", baseline.kg_co2], ["CO2 saved (%)", saved.kg_co2_pct],
      ["Note", view.note || ""]);
  }
  return rows;
}

const q = (v) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const toCsv = (rows) => rows.map(([k, v]) => `${q(k)},${q(v)}`).join("\n") + "\n";

export function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
