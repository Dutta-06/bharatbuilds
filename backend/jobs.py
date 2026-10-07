"""Jobs: parse a submission, place it with the scheduler, store and read it back."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from model import regions as region_config
from model.cost import Weights, receipt
from model.energy import gpu_tdp_w
from scheduler.greedy import Job, schedule
from scheduler.split import split

from . import db, forecasts
from .http import BadRequest


def _utc(text: str, name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        raise BadRequest(f"{name} must be an ISO date-time, e.g. 2026-10-10T18:00Z") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _num(body: dict, name: str, default=None, lo=None, hi=None, integer=False):
    value = body.get(name, default)
    if value is None:
        raise BadRequest(f"{name} is required")
    try:
        value = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{name} must be a number") from None
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise BadRequest(f"{name} must be between {lo} and {hi}")
    return value


def parse(body: dict, now: datetime) -> Job:
    known = region_config.load()
    gpu_hours = _num(body, "gpu_hours", lo=0.01, hi=10000)
    gpus = _num(body, "gpus", 1, lo=1, hi=1024, integer=True)
    gpu = str(body.get("gpu", "a100")).lower()
    try:
        gpu_tdp_w(gpu)
    except ValueError as e:
        raise BadRequest(str(e)) from None

    submit_region = body.get("submit_region", "ap-south-1")
    if submit_region not in known:
        raise BadRequest(f"submit_region must be one of {', '.join(known)}")
    allowed = body.get("allowed_regions")
    if allowed is not None:
        if not isinstance(allowed, list) or not allowed or not set(allowed) <= set(known):
            raise BadRequest(f"allowed_regions must be a non-empty list from {', '.join(known)}")
        allowed = tuple(allowed)

    if "deadline" in body:
        deadline = _utc(body["deadline"], "deadline")
    elif "deadline_h" in body:
        deadline = now + timedelta(hours=_num(body, "deadline_h", lo=0.1, hi=24 * 30))
    else:
        raise BadRequest("give deadline (ISO UTC) or deadline_h (hours from now)")

    w = body.get("weights") or {}
    try:
        weights = Weights(float(w.get("water", 0.5)), float(w.get("carbon", 0.5)))
    except (TypeError, ValueError) as e:
        raise BadRequest(f"weights: {e}") from None

    max_delay = body.get("max_delay_h")
    return Job(
        id=str(body.get("id") or uuid.uuid4().hex[:12]),
        gpu_hours=gpu_hours, gpus=gpus, gpu=gpu,
        submit_time=now, deadline=deadline, submit_region=submit_region,
        allowed_regions=allowed, data_residency=bool(body.get("data_residency", False)),
        max_delay_h=None if max_delay is None else _num(body, "max_delay_h", lo=0, hi=24 * 30),
        weights=weights,
    )


def submit(body: dict, now: datetime | None = None) -> dict:
    now = now or forecasts.utc_now()
    job = parse(body, now)
    surface, _ = forecasts.surface(start=now.replace(minute=0, second=0, microsecond=0))
    placement = schedule(job, surface)
    item = {
        "PK": db.job_pk(job.id), "SK": db.META,
        "GSI1PK": db.JOBS_INDEX_PK, "GSI1SK": f"{now:%Y-%m-%dT%H:%M:%S}#{job.id}",
        "job_id": job.id, "name": str(body.get("name", ""))[:80],
        "status": "placed" if placement.feasible else "infeasible",
        "submitted_at": f"{now:%Y-%m-%dT%H:%M:%SZ}",
        "request": {
            "gpu_hours": job.gpu_hours, "gpus": job.gpus, "gpu": job.gpu,
            "deadline": f"{job.deadline:%Y-%m-%dT%H:%MZ}", "submit_region": job.submit_region,
            "allowed_regions": list(job.allowed_regions) if job.allowed_regions else None,
            "data_residency": job.data_residency, "max_delay_h": job.max_delay_h,
            "weights": {"water": job.weights.water, "carbon": job.weights.carbon},
        },
        "it_kwh_estimated": round(job.it_kwh, 4),
        "duration_h": job.duration_h,
        "placement": placement.as_dict(submit_time=now),
    }
    if body.get("splittable"):
        max_chunks = _num(body, "max_chunks", 2, lo=1, hi=6, integer=True)
        plan = split(job, surface, max_chunks=max_chunks)
        if plan.get("feasible") and placement.baseline:
            b = placement.baseline.footprint
            plan["saved_vs_baseline"] = {
                "litres_pct": round(100 * (b.litres - plan["litres"]) / b.litres, 1) if b.litres else None,
                "kg_co2_pct": round(100 * (b.kg_co2 - plan["kg_co2"]) / b.kg_co2, 1) if b.kg_co2 else None,
            }
        plan["max_chunks"] = max_chunks
        plan["note"] = ("Advisory: the executor runs the single-window placement; running a split plan "
                        "(checkpoint, move, resume) is design-only. Checkpoint transfer is not costed.")
        item["split_plan"] = plan
    if placement.feasible:
        item["preview_receipt"] = receipt(placement.chosen.footprint, placement.baseline.footprint) \
            if placement.baseline else None
    db.put_item(item)
    return public(item)


def public(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK")}


def get(job_id: str) -> dict | None:
    item = db.get_item(db.job_pk(job_id), db.META)
    return public(item) if item else None


def queue(limit: int = 50) -> list[dict]:
    return [public(i) for i in db.recent_jobs(limit)]


def get_receipt(job_id: str) -> dict | None:
    """The final receipt once the executor has run the job (Step 7), else None."""
    item = db.get_item(db.receipt_pk(job_id), db.META)
    return public(item) if item else None
