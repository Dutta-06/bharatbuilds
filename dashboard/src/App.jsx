import React, { Suspense, lazy, useEffect, useState } from "react";
import Surface from "./pages/Surface.jsx";
import Submit from "./pages/Submit.jsx";
import Queue from "./pages/Queue.jsx";
import Job from "./pages/Job.jsx";
import Receipt from "./pages/Receipt.jsx";
import Savings from "./pages/Savings.jsx";
import Quality from "./pages/Quality.jsx";
import Policies from "./pages/Policies.jsx";
import Operations from "./pages/Operations.jsx";
import Assistant from "./pages/Assistant.jsx";
const Docs = lazy(() => import("./pages/Docs.jsx"));
import { api } from "./api.js";
import { THEMES, applyTheme, getTheme } from "./theme.js";
import { clock, parse, relative } from "./time.js";

const PAGES = [
  ["submit", "Submit"], ["queue", "Queue"], ["surface", "Surface"], ["savings", "Savings"],
  ["operations", "Power & Operations"], ["quality", "Forecasts"], ["assistant", "Assistant"], ["policies", "Policies"], ["docs", "Docs"],
];

const HELP = {
  submit: "guide-submit", queue: "guide-queue", surface: "guide-surface", savings: "guide-savings",
  quality: "data-and-forecasts", assistant: "guide-assistant", policies: "guide-policies",
  jobs: "guide-queue", receipt: "receipts",
  operations: "power-operations",
};

function useRoute() {
  const read = () => (window.location.hash.replace(/^#\/?/, "") || "submit").split("/");
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => { setRoute(read()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

/** One line that answers "is this data fresh?": when the forecast pipeline last ran. */
function Pulse() {
  const [run, setRun] = useState(null);
  useEffect(() => {
    let alive = true;
    const load = () => api.surface({ gpu_hours: 4 }).then((d) => alive && setRun({
      at: d.regions[0]?.run_id, n: d.regions.length,
      modelled: d.regions.some((r) => r.ci_sources?.includes("modelled")),
    })).catch(() => alive && setRun({ error: true }));
    load();
    const t = setInterval(load, 5 * 60 * 1000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  if (!run) return <span className="pulse"><span className="led" />checking forecasts</span>;
  if (run.error || !parse(run.at)) return <span className="pulse"><span className="led bad" />no forecast data</span>;
  const ageMin = (Date.now() - parse(run.at).getTime()) / 60000;
  const state = ageMin > 180 ? "bad" : ageMin > 90 || run.modelled ? "warn" : "good";
  return (
    <span className="pulse" title={`Last forecast run ${run.at}`}>
      <span className={`led ${state}`} />
      <span>forecast {clock(run.at)} <span className="muted">({relative(run.at)})</span></span>
      <span className="long muted">· {run.n} regions{run.modelled ? " · carbon modelled" : ""}</span>
    </span>
  );
}

function ThemeButton() {
  const [theme, setTheme] = useState(getTheme);
  const next = () => { const t = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]; applyTheme(t); setTheme(t); };
  return <button type="button" className="theme-btn" onClick={next} aria-label={`Theme: ${theme}. Switch theme`}>{theme}</button>;
}

export default function App() {
  const [page, arg, anchor] = useRoute();
  let body;
  if (page === "jobs" && arg) body = <Job id={decodeURIComponent(arg)} />;
  else if (page === "receipt" && arg) body = <Receipt id={decodeURIComponent(arg)} />;
  else if (page === "queue") body = <Queue />;
  else if (page === "surface") body = <Surface />;
  else if (page === "savings") body = <Savings />;
  else if (page === "quality") body = <Quality />;
  else if (page === "policies") body = <Policies />;
  else if (page === "operations") body = <Operations />;
  else if (page === "assistant") body = <Assistant />;
  else if (page === "docs") body = <Suspense fallback={<div className="muted">Loading documentation…</div>}><Docs slug={arg && decodeURIComponent(arg)} anchor={anchor} /></Suspense>;
  else body = <Submit />;
  const current = page === "jobs" || page === "receipt" ? "queue" : PAGES.some(([id]) => id === page) ? page : "submit";
  return (
    <>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>Skip to content</a>
      <header className="top">
        <div className="top-row">
          <a className="brand" href="#/submit"><b>Tidewise</b><span>water and carbon aware scheduling</span></a>
          <div className="top-tools"><Pulse /><ThemeButton /></div>
        </div>
        <nav className="tabs" aria-label="Sections">
          {PAGES.map(([id, label]) => <a key={id} href={`#/${id}`} aria-current={current === id ? "page" : undefined}>{label}</a>)}
        </nav>
      </header>
      <main id="main" tabIndex={-1}>{body}</main>
      {HELP[page] && (
        <footer className="help-foot">
          <a href={`#/docs/${HELP[page]}`}>Guide for this page</a><span aria-hidden="true">·</span><a href="#/docs/faq">FAQ</a><span aria-hidden="true">·</span><a href="#/docs">All documentation</a>
        </footer>
      )}
    </>
  );
}
