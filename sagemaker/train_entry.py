"""SageMaker training entry point: runs scripts/train_forecasts.py inside the container.

Launched by scripts/sagemaker_train.py. The source tarball puts this file next to model/,
forecasting/, sources/, scripts/ and data/regions.yaml. Optional carbon history arrives
in the "history" channel; the trained models and metrics.json are written to SM_MODEL_DIR,
which SageMaker uploads as model.tar.gz.
"""

import json
import os
import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def hyperparameters() -> dict:
    """SM_HPS holds each hyperparameter JSON-encoded as a string."""
    out = {}
    for k, v in json.loads(os.environ.get("SM_HPS", "{}")).items():
        try:
            out[k] = json.loads(v) if isinstance(v, str) else v
        except ValueError:
            out[k] = v
    return out


def main() -> int:
    hp = hyperparameters()
    history = Path(os.environ.get("SM_CHANNEL_HISTORY", "/opt/ml/input/data/history"))
    target = ROOT / "data" / "history"
    target.mkdir(parents=True, exist_ok=True)
    for csv_file in history.glob("*.csv") if history.is_dir() else []:
        shutil.copy(csv_file, target / csv_file.name)

    argv = ["train_forecasts.py", "--days", str(hp.get("days", 60))]
    if hp.get("regions"):
        argv += ["--regions", str(hp["regions"])]
    sys.argv = argv
    sys.path.insert(0, str(ROOT))
    try:
        runpy.run_path(str(ROOT / "scripts" / "train_forecasts.py"), run_name="__main__")
    except SystemExit as e:
        if e.code not in (0, None):
            raise

    out = Path(os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    out.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "forecasting" / "models").glob("*.json"):
        shutil.copy(f, out / f.name)
    print("model dir:", sorted(p.name for p in out.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
