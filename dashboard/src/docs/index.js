import manifest from "./manifest.json";

const files = import.meta.glob("./content/*.md", { query: "?raw", import: "default", eager: true });

export const groups = manifest.groups;
export const pages = groups.flatMap((g) => g.pages.map((p) => ({
  ...p, group: g.title, markdown: files[`./content/${p.slug}.md`] ?? "",
})));
export const bySlug = Object.fromEntries(pages.map((p) => [p.slug, p]));
