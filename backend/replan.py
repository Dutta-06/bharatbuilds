"""Re-plan a waiting job against the newest forecast.

Two uses: the nudge (an email when a much better window has opened) and
POST /jobs/{id}/reschedule (move the job there). Only jobs that are waiting for their start are
considered, and only plans inside the job's own constraints (regions, residency, deadline and
whatever is left of max_delay_h), so a reschedule can never break a rule the submitter set.
"""

from __future__ import annotations

import os
from datetime import datetime

from model.cost import cost, receipt
from scheduler.greedy import floor_hour, schedule

from . import db, forecasts, jobs
from .http import BadRequest

MIN_NUDGE_IMPROVEMENT = 0.15   # nudge only when the new plan costs at least 15% less than the current one
MIN_RESCHEDULE_IMPROVEMENT = 0.02


def _job_from_item(item: dict, now: datetime):
    r = item["request"]
    submitted = datetime.strptime(item["submitted_at"], "%Y-%m-%dT%H:%M:%SZ")
    body = {"id": item["job_id"], "gpu_hours": r["gpu_hours"], "gpus": r["gpus"], "gpu": r["gpu"],
            "deadline": r["deadline"], "submit_region": r["submit_region"],
            "allowed_regions": r.get("allowed_regions"), "data_residency": r.get("data_residency", False),
            "weights": r["weights"]}
    if r.get("max_delay_h") is not None:
        elapsed_h = max(0.0, (now - submitted).total_seconds() / 3600)
        body["max_delay_h"] = max(0.0, r["max_delay_h"] - elapsed_h)
    return jobs.parse(body, now)


def evaluate(item: dict, surface, now: datetime) -> dict | None:
    """A better plan for this waiting job, or None. improvement = how much cheaper (fraction)
    the new plan is than the current one, both priced on today's forecast."""
    chosen = (item.get("placement") or {}).get("chosen")
    if item.get("status") != "waiting" or not chosen:
        return None
    old_start = datetime.strptime(chosen["start"], "%Y-%m-%dT%H:%M")
    if old_start <= floor_hour(now):
        return None                                    # starting now
    job = _job_from_item(item, now)
    new = schedule(job, surface)
    if not new.feasible:
        return None
    best = new.chosen
    if (best.region, best.start) == (chosen["region"], old_start):
        return None
    d = job.duration_h
    if not surface.covers(chosen["region"], old_start, d):
        return None
    ref = (new.baseline.footprint, surface.regions[job.submit_region]) if new.baseline else None
    old_fp = surface.window(chosen["region"], old_start, d, job.it_kwh)
    old_cost = cost(old_fp, surface.regions[chosen["region"]], job.weights, baseline=ref)
    improvement = (old_cost - best.cost) / old_cost if old_cost > 0 else 0.0
    return {"placement": new, "old": {"region": chosen["region"], "start": chosen["start"], "footprint": old_fp},
            "improvement": improvement}


def _surface(now: datetime):
    return forecasts.surface(start=floor_hour(now))[0]


def message(item: dict, ev: dict, app_url: str = "") -> str:
    new, old = ev["placement"].chosen, ev["old"]
    link = f"{app_url.rstrip('/')}/#/jobs/{item['job_id']}" if app_url else f"job {item['job_id']}"
    return (
        f"A better window opened for {item.get('name') or item['job_id']}.\n\n"
        f"Now planned: {old['region']} at {old['start']} UTC\n"
        f"Better:      {new.region} at {new.start:%Y-%m-%dT%H:%M} UTC\n\n"
        f"On today's forecast the new plan scores {100 * ev['improvement']:.0f}% lower on your water/carbon "
        f"weights: about {old['footprint'].litres - new.footprint.litres:.2f} L less water and "
        f"{old['footprint'].kg_co2 - new.footprint.kg_co2:.3f} kg less CO2 (modelled).\n\n"
        f"To switch, open {link} and press \"Move to the better slot\". "
        f"If you do nothing, the job runs as planned.")


def nudge_all(now: datetime | None = None, publish=None, app_url: str | None = None) -> dict:
    """After each forecast run: email once per new better plan for each waiting job."""
    now = now or forecasts.utc_now()
    app_url = os.environ.get("APP_URL", "") if app_url is None else app_url
    waiting = [i for i in db.recent_jobs(500) if i.get("status") == "waiting"]
    if not waiting:
        return {"checked": 0, "nudged": []}
    surface = _surface(now)
    if publish is None:
        import boto3

        topic = os.environ["TOPIC_ARN"]
        sns = boto3.client("sns", endpoint_url=db.endpoint_url())
        publish = lambda subject, text: sns.publish(TopicArn=topic, Subject=subject, Message=text)  # noqa: E731
    nudged = []
    for item in waiting:
        ev = evaluate(item, surface, now)
        if not ev or ev["improvement"] < MIN_NUDGE_IMPROVEMENT:
            continue
        key = f"{ev['placement'].chosen.region}@{ev['placement'].chosen.start:%Y-%m-%dT%H:%M}"
        if item.get("nudged_for") == key:
            continue                                   # already told them about this exact plan
        publish("Pravaah: a better slot is available for your job", message(item, ev, app_url))
        item["nudged_for"] = key
        db.put_item(item)
        nudged.append(item["job_id"])
    return {"checked": len(waiting), "nudged": nudged}


def reschedule(job_id: str, now: datetime | None = None, sfn=None) -> dict:
    """Move a waiting job to a better plan. Stops its Step Functions run, rewrites the plan,
    starts a new run. If the old run cannot be stopped nothing is changed (no double runs)."""
    now = now or forecasts.utc_now()
    item = db.get_item(db.job_pk(job_id), db.META)
    if item is None:
        raise BadRequest(f"no job {job_id}", 404)
    if item["status"] != "waiting":
        raise BadRequest(f"job is {item['status']}; only a job waiting for its start can be rescheduled", 409)
    ev = evaluate(item, _surface(now), now)
    if ev is None or ev["improvement"] < MIN_RESCHEDULE_IMPROVEMENT:
        return {"rescheduled": False, "job_id": job_id,
                "reason": "no better window within this job's constraints right now"}

    original = dict(item)
    placement = ev["placement"]
    n = int(item.get("reschedules", 0)) + 1
    item.update(
        placement=placement.as_dict(submit_time=now), status="placed", reschedules=n,
        rescheduled_at=f"{now:%Y-%m-%dT%H:%M:%SZ}",
        preview_receipt=receipt(placement.chosen.footprint, placement.baseline.footprint) if placement.baseline else None)
    item.pop("nudged_for", None)

    arn = os.environ.get("RUN_STATE_MACHINE_ARN")
    if arn:
        import boto3

        sfn = sfn or boto3.client("stepfunctions", endpoint_url=db.endpoint_url())
        old_name = f"job-{job_id}" if n == 1 else f"job-{job_id}-r{n - 1}"
        try:
            sfn.stop_execution(executionArn=arn.replace(":stateMachine:", ":execution:") + ":" + old_name,
                               cause="rescheduled to a better window")
        except Exception as e:                         # an already-finished or missing run is fine
            if type(e).__name__ not in ("ExecutionDoesNotExist", "ExecutionAlreadyStarted") \
                    and "does not exist" not in str(e).lower():
                raise BadRequest(f"could not stop the current run ({type(e).__name__}); nothing was changed", 502) from e
        db.put_item(item)
        try:
            import json
            sfn.start_execution(stateMachineArn=arn, name=f"job-{job_id}-r{n}", input=json.dumps({"job_id": job_id}))
        except Exception as e:
            db.put_item(original)
            raise BadRequest(f"could not start the new run ({type(e).__name__}); the old plan was restored "
                             "but its run was stopped, resubmit the job", 502) from e
    else:
        db.put_item(item)
    chosen = placement.chosen
    return {"rescheduled": True, "job_id": job_id, "improvement": round(ev["improvement"], 3),
            "from": {"region": ev["old"]["region"], "start": ev["old"]["start"]},
            "to": {"region": chosen.region, "start": f"{chosen.start:%Y-%m-%dT%H:%M}"}}
