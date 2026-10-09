import test from "node:test";
import assert from "node:assert/strict";
import { buildIndex, search, sections } from "./search.js";

const pages = [
  { slug: "a", title: "Receipts", markdown: "# Receipts\n\nIntro text.\n\n## Share a receipt\n\nUse the **Copy link** button." },
  { slug: "b", title: "Regions", markdown: "# Regions\n\nMumbai uses cooling towers.\n\n## Residency\n\nKeeps data in one jurisdiction." },
];
const index = buildIndex(pages);

test("sections split on second-level headings", () => {
  assert.deepEqual(sections(pages[0].markdown).map((s) => s.heading), ["", "Share a receipt"]);
});
test("heading matches rank above body matches", () => {
  const r = search(index, "receipt");
  assert.equal(r[0].slug, "a");
});
test("prefix and multi-word queries", () => {
  assert.equal(search(index, "jurisd")[0].heading, "Residency");
  assert.equal(search(index, "cooling towers")[0].slug, "b");
});
test("all words must match, empty query returns nothing", () => {
  assert.deepEqual(search(index, "cooling receipts"), []);
  assert.deepEqual(search(index, "  "), []);
});
test("snippets are plain text", () => {
  assert.ok(!search(index, "copy")[0].snippet.includes("*"));
});
