import React, { useState } from "react";
import { api } from "../api.js";
import { ErrorBox } from "./common.jsx";

export default function Assistant() {
  const [message, setMessage] = useState("");
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function send(e) {
    e.preventDefault();
    if (!message.trim()) return;
    setBusy(true); setError(null);
    const q = message; setMessage("");
    try {
      const resp = await fetch(`${api.base}/chat`, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: q }) });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || body.message || `API error ${resp.status}`);
      setLog((l) => [...l, { q, a: body.reply, calls: body.tool_calls }]);
    } catch (err) { setError(err); setMessage(q); } finally { setBusy(false); }
  }
  return (
    <>
      <h1>Assistant</h1>
      <p className="lede">Ask in plain language, for example: “run this 8-GPU-hour job by Friday with least water”, or
        “where would 2 GPU-hours be cheapest tonight?”</p>
      <ErrorBox error={error} />
      {log.map((t, i) => (
        <div className="card" key={i}>
          <div className="muted small">You</div><div>{t.q}</div>
          <div className="muted small" style={{ marginTop: 8 }}>Pravaah</div><div>{t.a}</div>
          {t.calls?.some((c) => c.tool === "submit_job") && <p className="small"><a href="#/queue">See it in the queue →</a></p>}
        </div>
      ))}
      <form className="card" onSubmit={send}>
        <label>Message<input type="text" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={2000} /></label>
        <button className="primary" disabled={busy}>{busy ? "Thinking…" : "Send"}</button>
      </form>
    </>
  );
}
