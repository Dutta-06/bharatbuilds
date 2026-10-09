"""The in-app docs must stay in step with the code: manifest, links, API routes, branding."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "dashboard" / "src" / "docs"
CONTENT = DOCS / "content"
MANIFEST = json.loads((DOCS / "manifest.json").read_text())
SLUGS = [p["slug"] for g in MANIFEST["groups"] for p in g["pages"]]


def test_manifest_matches_content_files():
    assert len(SLUGS) == len(set(SLUGS))
    assert set(SLUGS) == {p.stem for p in CONTENT.glob("*.md")}


def test_every_page_has_title_and_summary():
    for g in MANIFEST["groups"]:
        for p in g["pages"]:
            assert p["title"] and p["summary"], p
            first = (CONTENT / f"{p['slug']}.md").read_text().splitlines()[0]
            assert first.startswith("# "), p["slug"]


def test_internal_links_resolve():
    for md in CONTENT.glob("*.md"):
        for slug in re.findall(r"\]\(#/docs/([a-z0-9-]+)", md.read_text()):
            assert slug in SLUGS, f"{md.name} links to missing page {slug}"


def test_api_page_covers_every_route():
    template = (ROOT / "template.yaml").read_text()
    routes = set(re.findall(r"Path:\s*\"?(/[^\s,\"}]*)\"?,\s*Method:\s*(\w+)", template))
    assert routes
    api = (CONTENT / "api.md").read_text()
    for path, method in routes:
        assert f"| `{method.upper()}` | `{path}` |" in api, f"api.md misses {method.upper()} {path}"


def test_no_old_product_name():
    for md in CONTENT.glob("*.md"):
        assert "pravaah" not in md.read_text().lower(), md.name
