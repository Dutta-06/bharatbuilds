import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { ErrorBox, PageHead } from "./common.jsx";

const EXAMPLES = [
  "Run this 8-GPU-hour job by Friday with least water",
  "Where would 2 GPU-hours be cheapest tonight?",
  "Keep a 4 GPU-hour job in India, done within 12 hours",
];

export default function Assistant() {
  const [message, setMessage] = useState("");
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [log, busy]);
  async function send(text) {
    const q = (text ?? message).trim();
    if (!q || busy) return;
    setBusy(true); setError(null); setMessage("");
    try {
      const resp = await fetch(`${api.base}/chat`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ message: q }) });
      const body = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(body.error || body.message || (resp.status >= 500 ? "The assistant could not answer. Try again in a moment, or use the Submit page." : `API error ${resp.status}`));
      setLog((l) => [...l, { q, a: body.reply, calls: body.tool_calls }]);
    } catch (err) { setError(err); setMessage(q); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHead title="Assistant">
        Describe the job the way you would to a colleague. The assistant reads the live cost surface and can submit the job for you, so
        say whether you want it run or only priced.
      </PageHead>
      <div className="chat" aria-live="polite">
        {log.length === 0 && (
          <div className="stack">
            <div className="section-title" style={{ margin: 0 }}>Try</div>
            <div className="chips">{EXAMPLES.map((e) => <button key={e} type="button" className="chip" onClick={() => send(e)} disabled={busy}>{e}</button>)}</div>
          </div>)}
        {log.map((t, i) => (
          <React.Fragment key={i}>
            <div className="msg you"><div className="who">You</div><div className="body">{t.q}</div></div>
            <div className="msg bot"><div className="who">Tidewise</div><div className="body">{t.a}
              {t.calls?.some((c) => c.tool === "submit_job") && <p className="small" style={{ marginTop: 8 }}><a href="#/queue">Open the queue to see it</a></p>}</div></div>
          </React.Fragment>))}
        {busy && <div className="msg bot"><div className="who">Tidewise</div><div className="body muted">Reading the forecast…</div></div>}
        <div ref={end} />
      </div>
      <ErrorBox error={error} />
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="sr" htmlFor="msg">Message</label>
        <input id="msg" type="text" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={2000} placeholder="Describe a job…" autoComplete="off" />
        <button className="primary" disabled={busy || !message.trim()}>Send</button>
      </form>
    </>
  );
}
