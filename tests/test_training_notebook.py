import base64
import json
import sys

from tests.api.conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import build_training_notebook as nb  # noqa: E402


def test_committed_notebook_is_fresh():
    assert nb.OUT.read_text(encoding="utf-8") == nb.notebook(), \
        "notebook is stale: run python scripts/build_training_notebook.py and commit it"


def test_notebook_is_valid_and_self_contained():
    data = json.loads(nb.OUT.read_text(encoding="utf-8"))
    assert data["nbformat"] == 4 and all("id" in c for c in data["cells"])
    unpack = next(c for c in data["cells"] if c["cell_type"] == "code" and "FILES = " in "".join(c["source"]))
    ns: dict = {}
    text = "".join(unpack["source"]).split("ROOT = pathlib.Path")[0]       # just the FILES dict
    exec(text, ns)                                                          # noqa: S102 (our own generated cell)
    assert set(ns["FILES"]) == set(nb.EMBED)
    assert b"Gradient" in base64.b64decode(ns["FILES"]["forecasting/evaluate.py"])


def test_embedded_modules_import_only_what_is_embedded():
    """Every first-party module the embedded files import must itself be embedded."""
    import re

    embedded = {p.split("/")[0] for p in nb.EMBED}
    for rel in nb.EMBED:
        if not rel.endswith(".py"):
            continue
        for mod in re.findall(r"^(?:from|import) (backend|model|forecasting|sources|scheduler|functions)\b",
                              (ROOT / rel).read_text(encoding="utf-8"), flags=re.M):
            assert mod in embedded, f"{rel} imports {mod}, which the notebook does not embed"
