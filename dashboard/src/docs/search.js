// Client-side docs search. Pure functions so they can be tested with `node --test`.

const words = (s) => s.toLowerCase().match(/[a-z0-9₂]+/g) || [];

/** Strip Markdown to plain text for matching and snippets. */
export function plain(md) {
  return md
    .replace(/```[\s\S]*?```/g, (m) => m.replace(/```\w*/g, " "))
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[`*_>|#]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Split a page into sections at "## " headings so results can point at a heading. */
export function sections(md) {
  const out = [];
  let cur = { heading: "", lines: [] };
  for (const line of md.split("\n")) {
    const m = /^##\s+(.*)/.exec(line);
    if (m) { out.push(cur); cur = { heading: m[1].trim(), lines: [] }; } else cur.lines.push(line);
  }
  out.push(cur);
  return out.map((s) => ({ heading: s.heading, text: plain(s.lines.join("\n")) })).filter((s) => s.text || s.heading);
}

export function buildIndex(pages) {
  return pages.flatMap((p) => sections(p.markdown).map((s) => ({
    slug: p.slug, page: p.title, heading: s.heading, text: s.text, hay: words(`${p.title} ${s.heading} ${s.text}`),
  })));
}

function snippet(text, terms) {
  const lower = text.toLowerCase();
  const at = terms.map((t) => lower.indexOf(t)).filter((i) => i >= 0).sort((a, b) => a - b)[0] ?? 0;
  const start = Math.max(0, at - 40);
  return (start ? "…" : "") + text.slice(start, start + 140).trim() + (start + 140 < text.length ? "…" : "");
}

/** Every query word must match (prefix match). Title and heading hits rank above body hits. */
export function search(index, query, limit = 8) {
  const terms = words(query);
  if (!terms.length) return [];
  const scored = [];
  for (const e of index) {
    const head = words(`${e.page} ${e.heading}`);
    let score = 0;
    let ok = true;
    for (const t of terms) {
      const inHead = head.some((w) => w.startsWith(t));
      const inBody = e.hay.some((w) => w.startsWith(t));
      if (!inHead && !inBody) { ok = false; break; }
      score += inHead ? 5 : 1;
    }
    if (ok) scored.push({ ...e, score });
  }
  scored.sort((a, b) => b.score - a.score || a.page.localeCompare(b.page));
  return scored.slice(0, limit).map((e) => ({ slug: e.slug, page: e.page, heading: e.heading, snippet: snippet(e.text, terms) }));
}
