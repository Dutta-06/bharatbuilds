import React, { useEffect, useMemo, useRef, useState } from "react";
import { groups, pages, bySlug } from "../docs/index.js";
import { renderPage } from "../docs/render.js";
import { buildIndex, search } from "../docs/search.js";

const index = buildIndex(pages);
const href = (slug, anchor) => `#/docs/${slug}${anchor ? `/${anchor}` : ""}`;

function SearchBox() {
  const [q, setQ] = useState("");
  const results = useMemo(() => search(index, q), [q]);
  return (
    <div className="docs-search">
      <label className="sr-only" htmlFor="docs-q">Search the documentation</label>
      <input id="docs-q" type="search" value={q} placeholder="Search the docs" autoComplete="off"
        onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setQ("")} />
      {q.trim() && (
        <ul className="docs-results" aria-label="Search results">
          {results.length === 0 && <li className="muted">No matches for "{q.trim()}".</li>}
          {results.map((r, i) => (
            <li key={i}>
              <a href={href(r.slug)} onClick={() => setQ("")}>
                <b>{r.page}</b>{r.heading && <span className="muted"> / {r.heading}</span>}
                <span className="snip">{r.snippet}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Sidebar({ current }) {
  return (
    <nav className="docs-nav" aria-label="Documentation">
      {groups.map((g) => (
        <div key={g.title}>
          <div className="section-title">{g.title}</div>
          <ul>
            {g.pages.map((p) => (
              <li key={p.slug}><a href={href(p.slug)} aria-current={p.slug === current ? "page" : undefined}>{p.title}</a></li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function Home() {
  return (
    <div className="stack">
      <header className="page-head">
        <div className="eyebrow">Documentation</div>
        <h1>Learn Tidewise</h1>
        <p className="lede">Guides, concepts and reference for placing AI jobs where and when they use the least water and carbon.</p>
      </header>
      <div className="docs-cards">
        {groups.map((g) => (
          <section key={g.title} className="panel">
            <h2>{g.title}</h2>
            <ul className="docs-list">
              {g.pages.map((p) => (
                <li key={p.slug}><a href={href(p.slug)}>{p.title}</a><span className="muted">{p.summary}</span></li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function Article({ page, anchor }) {
  const { html, toc } = useMemo(() => renderPage(page.slug, page.markdown), [page]);
  const ref = useRef(null);
  const i = pages.findIndex((p) => p.slug === page.slug);
  const prev = pages[i - 1], next = pages[i + 1];

  useEffect(() => {
    document.title = `${page.title} · Tidewise docs`;
    const root = ref.current;
    if (!root) return;
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.querySelector(".copy")) return;
      const b = document.createElement("button");
      b.type = "button"; b.className = "copy"; b.textContent = "Copy";
      b.onclick = () => navigator.clipboard?.writeText(pre.querySelector("code")?.innerText ?? pre.innerText)
        .then(() => { b.textContent = "Copied"; setTimeout(() => { b.textContent = "Copy"; }, 1500); }).catch(() => {});
      pre.appendChild(b);
    });
    const target = anchor && document.getElementById(anchor);
    if (target) {
      target.scrollIntoView();
      target.classList.add("flash");
      setTimeout(() => target.classList.remove("flash"), 1700);
    } else window.scrollTo(0, 0);
    return () => { document.title = "Tidewise"; };
  }, [page, anchor]);

  return (
    <div className="docs-body">
      <article className="doc" ref={ref}>
        <div className="eyebrow">{page.group}</div>
        <div dangerouslySetInnerHTML={{ __html: html }} />
        <footer className="doc-foot">
          {prev ? <a href={href(prev.slug)}><span className="muted">Previous</span>{prev.title}</a> : <span />}
          {next ? <a href={href(next.slug)} className="next"><span className="muted">Next</span>{next.title}</a> : <span />}
        </footer>
      </article>
      {toc.length > 0 && (
        <aside className="doc-toc" aria-label="On this page">
          <div className="section-title">On this page</div>
          <ul>{toc.map((t) => <li key={t.id} className={`d${t.depth}`}><a href={href(page.slug, t.id)}>{t.text}</a></li>)}</ul>
        </aside>
      )}
    </div>
  );
}

export default function Docs({ slug, anchor }) {
  const page = slug ? bySlug[slug] : null;
  return (
    <div className="docs">
      <div className="docs-side">
        <SearchBox />
        <details className="docs-menu" key={slug || "home"}>
          <summary>All pages</summary>
          <Sidebar current={slug} />
        </details>
        <div className="docs-fixed"><Sidebar current={slug} /></div>
      </div>
      <div className="docs-main">
        {!slug ? <Home /> : page ? <Article page={page} anchor={anchor} /> : (
          <div className="stack">
            <h1>Page not found</h1>
            <p>There is no documentation page called "{slug}". <a href="#/docs">Browse all pages</a>.</p>
          </div>
        )}
      </div>
    </div>
  );
}
