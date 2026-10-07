"""The assistant's three tools, as plain functions over the deployed HTTP API.

Kept free of the Strands import so they are testable (and reusable) without it;
assistant/agent.py wraps them with strands.tool.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

CALLS: list[dict] = []   # every tool call this process made (the eval reads it)


def api_base() -> str:
    return os.environ.get("PRAVAAH_API_URL", "http://localhost:3000").rstrip("/")


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(api_base() + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", "User-Agent": "pravaah-assistant"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.load(e).get("error", f"HTTP {e.code}"), "status": e.code}
        except Exception:
            return {"error": f"HTTP {e.code}", "status": e.code}


def get_surface(gpu_hours: float = 1.0, w_water: float = 0.5, w_carbon: float = 0.5,
                baseline: str = "ap-south-1") -> dict:
    """Cost of running gpu_hours in every region, hour by hour, for the next 48 h. Summarised:
    the best slot, the baseline (run now in `baseline`), and each region's cheapest hour."""
    CALLS.append({"tool": "get_surface", "args": {"gpu_hours": gpu_hours, "w_water": w_water,
                                                   "w_carbon": w_carbon, "baseline": baseline}})
    raw = _call("GET", "/surface?" + urllib.parse.urlencode(
        {"gpu_hours": gpu_hours, "w_water": w_water, "w_carbon": w_carbon, "baseline": baseline}))
    if "error" in raw:
        return raw
    best_per_region = []
    for r in raw["regions"]:
        cell = min(r["cells"], key=lambda c: c["cost"])
        best_per_region.append({"region": r["id"], "hour": cell["hour"], "cost": cell["cost"],
                                "litres": cell["litres"], "kg_co2": cell["kg_co2"]})
    return {"best": raw["best"], "baseline": raw["baseline"], "window_end": raw["window_end"],
            "best_per_region": sorted(best_per_region, key=lambda x: x["cost"]),
            "data_sources": sorted({s for r in raw["regions"] for s in r["weather_sources"] + r["ci_sources"]})}


def submit_job(gpu_hours: float, deadline: str | None = None, deadline_h: float | None = None,
               submit_region: str = "ap-south-1", gpus: int = 1, gpu: str = "a100",
               water_weight: float = 0.5, carbon_weight: float = 0.5,
               allowed_regions: list[str] | None = None, data_residency: bool = False,
               name: str = "") -> dict:
    """Submit a job; Pravaah places it immediately. Give `deadline` (ISO 8601 UTC) or
    `deadline_h` (hours from now). Returns the placement and its plain-language reason."""
    body = {"gpu_hours": gpu_hours, "gpus": gpus, "gpu": gpu, "submit_region": submit_region,
            "weights": {"water": water_weight, "carbon": carbon_weight}, "data_residency": data_residency,
            "name": name or "via assistant"}
    if deadline:
        body["deadline"] = deadline
    if deadline_h is not None:
        body["deadline_h"] = deadline_h
    if allowed_regions:
        body["allowed_regions"] = allowed_regions
    CALLS.append({"tool": "submit_job", "args": body})
    raw = _call("POST", "/jobs", body)
    if "error" in raw:
        return raw
    p = raw["placement"]
    return {"job_id": raw["job_id"], "status": raw["status"], "reason": p["reason"],
            "chosen": p.get("chosen"), "saved": (raw.get("preview_receipt") or {}).get("saved")}


def get_receipt(job_id: str) -> dict:
    """The receipt for a job: final (measured) once it has run, otherwise the modelled preview."""
    CALLS.append({"tool": "get_receipt", "args": {"job_id": job_id}})
    return _call("GET", f"/jobs/{urllib.parse.quote(job_id)}/receipt")
