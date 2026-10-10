"""Build notebooks/train_forecasts_colab.ipynb: scripts/train_forecasts.py as a standalone Colab notebook.

    python scripts/build_training_notebook.py          # rewrite the notebook
    python scripts/build_training_notebook.py --check  # exit 1 if the committed notebook is stale

The notebook embeds the few modules training needs (so Colab needs no repo access), unpacks them
to /content/pravaah, runs the real scripts/train_forecasts.py, shows the verdict per model, and
downloads the models as a zip. tests/test_training_notebook.py fails if it goes stale.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebooks" / "train_forecasts_colab.ipynb"

# Everything train_forecasts.py imports, and nothing else (no tests, no models, no AWS code).
EMBED = (["data/regions.yaml", "scripts/train_forecasts.py", "sources/__init__.py", "sources/openmeteo.py"]
         + [f"model/{n}" for n in ("__init__.py", "coefficients.py", "coefficients.yaml", "regions.py", "wetbulb.py")]
         + [f"forecasting/{n}" for n in ("__init__.py", "evaluate.py", "features.py", "trees.py")])


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str, form: bool = False) -> dict:
    meta = {"cellView": "form"} if form else {}
    return {"cell_type": "code", "metadata": meta, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


def cells() -> list[dict]:
    # All embedded inputs are text. Git may check them out as CRLF on Windows;
    # normalize before hashing/embedding so freshness checks are reproducible.
    files = {p: base64.b64encode((ROOT / p).read_text(encoding="utf-8").encode("utf-8")).decode() for p in EMBED}
    blob = json.dumps(files, indent=0)
    return [
        md("""
# Tidewise: train the forecast models

Trains the gradient-boosted **wet-bulb** and **carbon** models for every region, judges each against two
baselines (persistence and the provider's own forecast) on the last 7 days, and keeps a model **only if it
beats both**. The kept models are tiny JSON files that the deployed `predict` Lambda loads.

**Run all** (Runtime → Run all). It takes a few minutes. At the end it downloads `forecast-models.zip`.

What you need:
- Internet (Colab has it). Weather comes from Open-Meteo's free API, which has a daily request quota per
  IP address. If a cell fails with *429 / Daily API request limit exceeded*, wait until 00:00 UTC and rerun.
- *Optional, for carbon models:* real carbon history. The deployed pipeline saves it to S3; carbon models are
  skipped until at least 10 days exist. See the upload cell below. Weather models need nothing extra.
"""),
        code("!pip -q install scikit-learn pyyaml pandas"),
        code("#@title Unpack the project files (embedded; nothing to edit)\n"
             "import base64, pathlib\n\n"
             f"FILES = {blob}\n\n"
             "ROOT = pathlib.Path('/content/pravaah')\n"
             "for rel, data in FILES.items():\n"
             "    path = ROOT / rel\n"
             "    path.parent.mkdir(parents=True, exist_ok=True)\n"
             "    path.write_bytes(base64.b64decode(data))\n"
             "print(f'unpacked {len(FILES)} files to {ROOT}')\n", form=True),
        md("""
## Settings
`DAYS` is how much weather history to train on. Leave `REGIONS` empty for all 8 regions, or list some,
e.g. `'eu-north-1,ap-south-1'`, to test quickly.
"""),
        code("DAYS = 60\nREGIONS = ''   # '' = all regions\n"),
        md("""
## Optional: carbon history
Skip this cell unless you have synced the history from S3
(`aws s3 sync s3://<BucketName>/history data/history`). Upload the `<region>.csv` files here and carbon
models get trained too. Without them, carbon is reported as *skipped: not enough real history yet*.
"""),
        code("""
import pathlib
try:
    from google.colab import files
    up = files.upload()
    hist = pathlib.Path('/content/pravaah/data/history'); hist.mkdir(parents=True, exist_ok=True)
    for name, data in up.items():
        (hist / name).write_bytes(data)
    print('saved', sorted(up))
except ImportError:
    print('not running in Colab; copy your CSVs into /content/pravaah/data/history yourself')
"""),
        md("## Train and judge"),
        code("""
import subprocess, sys
cmd = [sys.executable, 'scripts/train_forecasts.py', '--days', str(DAYS)] + (['--regions', REGIONS] if REGIONS else [])
run = subprocess.run(cmd, cwd='/content/pravaah', capture_output=True, text=True)
print(run.stdout)
if run.returncode:
    print(run.stderr[-2000:])
    raise SystemExit('training failed (see above). A 429 means the Open-Meteo daily quota: retry after 00:00 UTC.')
"""),
        md("""
## Verdicts
`use_model = True` means the model beat **both** baselines on the held-out week and will be shipped.
Quote this table honestly in the blog and video, including the models that were **not** used.
"""),
        code("""
import json, pandas as pd
m = json.load(open('/content/pravaah/forecasting/models/metrics.json'))
print('trained at', m['trained_at'], '| held-out days:', m['test_days'])
rows = [r for r in m['results']]
df = pd.DataFrame(rows)
cols = [c for c in ('region', 'target', 'n_train', 'n_test', 'mae_model', 'mae_persistence', 'mae_provider', 'use_model', 'skipped') if c in df]
df[cols]
"""),
        md("## Download"),
        code("""
import pathlib, shutil
models = pathlib.Path('/content/pravaah/forecasting/models')
print('models kept:', sorted(p.name for p in models.glob('*-*.json')) or 'none (no model beat both baselines)')
shutil.make_archive('/content/forecast-models', 'zip', models)
try:
    from google.colab import files
    files.download('/content/forecast-models.zip')
except ImportError:
    print('zip at /content/forecast-models.zip')
"""),
        md("""
## Next
1. Unzip into the repo's `forecasting/models/` (replace what is there; delete model files that are not in the zip).
2. Commit them and open a PR.
3. Redeploy so the Lambda picks them up (`make build`, then `sam deploy`). The `predict` step uses only files
   whose verdict says `use_model: true`.
"""),
    ]


def notebook() -> str:
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"colab": {"provenance": []}, "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}},
          "cells": cells()}
    for i, c in enumerate(nb["cells"]):
        c["id"] = f"cell{i:02d}"
    return json.dumps(nb, indent=1) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    text = notebook()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("notebooks/train_forecasts_colab.ipynb is stale: run python scripts/build_training_notebook.py",
                  file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text) // 1024} KiB, {len(EMBED)} files embedded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
