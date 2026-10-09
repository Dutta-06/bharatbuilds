import { Marked } from "marked";

export const slugify = (s) => s.toLowerCase().replace(/<[^>]+>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** Render one docs page. Headings get ids, and the TOC lists the h2/h3 headings. */
export function renderPage(slug, markdown) {
  const toc = [];
  const seen = new Set();
  const marked = new Marked({
    renderer: {
      heading({ tokens, depth }) {
        const text = this.parser.parseInline(tokens);
        let id = slugify(text) || "section";
        while (seen.has(id)) id += "-2";
        seen.add(id);
        if (depth === 2 || depth === 3) toc.push({ id, depth, text: text.replace(/<[^>]+>/g, "") });
        if (depth === 1) return `<h1>${text}</h1>`;
        return `<h${depth} id="${id}">${text}<a class="anchor" href="#/docs/${slug}/${id}" aria-label="Link to this section">#</a></h${depth}>`;
      },
    },
  });
  return { html: marked.parse(markdown), toc };
}
