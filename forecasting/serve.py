"""Apply trained models (if any beat their baselines) to a region's fetched rows."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .features import carbon_row, wetbulb_row
from .trees import predict_one

MODELS = Path(__file__).resolve().parent / "models"


@lru_cache(maxsize=None)
def load(region: str, target: str) -> dict | None:
    """The exported model, only if training marked it use_model (it beat both baselines)."""
    path = MODELS / f"{region}-{target}.json"
    if not path.exists():
        return None
    model = json.loads(path.read_text())
    return model if model.get("verdict", {}).get("use_model") else None


def apply(region: str, rows: list[dict], yesterday: dict[str, float] | None = None) -> list[dict]:
    """Return rows with model predictions where a model is in use; provider values kept alongside."""
    wb = load(region, "t_wb")
    ci = load(region, "ci")
    yesterday = yesterday or {}
    out = []
    last_ci = rows[0]["ci_g_per_kwh"] if rows else None
    for lead, r in enumerate(rows):
        r = dict(r)
        if wb is not None:
            # recent_residual is unknown at serve time without observations; 0 = "no recent bias".
            x = wetbulb_row(r["hour"], lead, r["t_wb"], r["t_db"], r["rh"], recent_residual=0.0)
            r["t_wb_provider"] = r["t_wb"]
            r["t_wb"] = round(predict_one(wb, [x[f] for f in wb["features"]]), 2)
            r["t_wb_source"] = "model"
        # Only replace carbon where it is a held latest value (no real forecast to beat).
        if ci is not None and r.get("ci_source") == "electricitymaps-latest-held" and last_ci is not None:
            x = carbon_row(r["hour"], lead, last_ci, yesterday.get(r["hour"]))
            r["ci_provider"] = r["ci_g_per_kwh"]
            r["ci_g_per_kwh"] = round(predict_one(ci, [x[f] for f in ci["features"]]), 1)
            r["ci_source"] = "model"
        out.append(r)
    return out
