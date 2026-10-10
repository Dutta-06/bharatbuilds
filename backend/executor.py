"""Steps of the pravaah-run state machine (load, launch, finish, fail).

launch() runs the worker in the chosen region:
- If a `pravaah-worker` function is deployed there (WORKER_FUNCTION_NAME), it is
  invoked cross-region and reports the region it really ran in.
- Otherwise (local runs, or a region without a worker) the worker code runs in
  this function and the receipt records ran_in = this region and
  requested_region = the chosen one. It never pretends.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from model import coefficients as c
from model.cost import Footprint, receipt, rescale

from . import db, jobs

WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "pravaah-worker")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _update_status(job_id: str, status: str, **fields) -> None:
    names = {"#s": "status"}
    values = {":s": status, ":t": _now()}
    sets = ["#s = :s", "updated_at = :t"]
    # Facility snapshots condition on this version. Even same-status updates
    # must invalidate an older snapshot (e.g. saving the worker result).
    existing = jobs.get(job_id)
    if existing and existing.get("facility_id"):
        sets.append("power_version = if_not_exists(power_version, :zero) + :one")
        values.update({":zero": 0, ":one": 1})
    for i, (k, v) in enumerate(fields.items()):
        names[f"#f{i}"] = k
        values[f":v{i}"] = db.to_dynamo(v)
        sets.append(f"#f{i} = :v{i}")
    db.table().update_item(Key={"PK": db.job_pk(job_id), "SK": db.META},
                           UpdateExpression="SET " + ", ".join(sets),
                           ExpressionAttributeNames=names, ExpressionAttributeValues=values)


def load(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise ValueError(f"no job {job_id}")
    out = {"job_id": job_id, "status": job["status"], "reason": job["placement"]["reason"]}
    chosen = job["placement"].get("chosen")
    if chosen and job["status"] in {"placed", "waiting"}:
        out.update(status="waiting", region=chosen["region"], start=chosen["start"], end=chosen["end"],
                   wait_until=chosen["start"] + ":00Z")
        db.table().update_item(Key={"PK": db.job_pk(job_id), "SK": db.META},
                               UpdateExpression="SET #s = :waiting",
                               ConditionExpression="#s IN (:placed, :waiting)",
                               ExpressionAttributeNames={"#s": "status"},
                               ExpressionAttributeValues={":placed": "placed", ":waiting": "waiting"})
    return out


def run_worker(region: str, job_id: str, seconds: float) -> dict:
    payload = {"job_id": job_id, "seconds": seconds}
    home = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if os.environ.get("WORKER_MODE", "auto") != "inline":
        try:
            client = boto3.client("lambda", region_name=region, endpoint_url=db.endpoint_url(),
                                  config=Config(retries={"total_max_attempts": 1}))
            resp = client.invoke(FunctionName=WORKER_FUNCTION_NAME, Payload=json.dumps(payload).encode())
            result = json.loads(resp["Payload"].read())
            if "errorMessage" not in result:
                return {**result, "launched_via": "cross-region-lambda", "requested_region": region}
            raise RuntimeError("worker invocation returned an error; execution is uncertain, no fallback launch")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise  # A timeout/service failure must not start an additional proxy.
            fallback_reason = f"{type(e).__name__}: {e}"[:200]
    else:
        fallback_reason = "WORKER_MODE=inline"
    result = _inline_worker().handler(payload, None)
    return {**result, "region": home, "launched_via": "inline-fallback",
            "requested_region": region, "fallback_reason": fallback_reason}


def _inline_worker():
    """functions/worker/app.py: copied into the layer as worker_inline.py by `make layer`."""
    try:
        import worker_inline
        return worker_inline
    except ImportError:
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "functions" / "worker" / "app.py"
        spec = importlib.util.spec_from_file_location("worker_inline", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def launch(job_id: str, region: str) -> dict:
    job = jobs.get(job_id)
    if job is None or job.get("execution_mode") == "SIMULATED_FACILITY":
        raise ValueError("cloud executor cannot launch a simulated or missing workload")
    if job.get("worker_result"):
        return job["worker_result"]
    if job["status"] not in {"placed", "waiting"}:
        raise ValueError("job already launched or completed; duplicate launch rejected")
    values = {":placed": "placed", ":waiting": "waiting", ":running": "running", ":r": region}
    update = {"TableName": db.table_name(), "Key": {"PK": db.job_pk(job_id), "SK": db.META},
              "UpdateExpression": "SET #s = :running, ran_in_requested = :r",
              "ConditionExpression": "#s IN (:placed, :waiting)",
              "ExpressionAttributeNames": {"#s": "status"}, "ExpressionAttributeValues": values}
    if job.get("facility_id"):
        from . import facilities
        f = facilities.reevaluate(job["facility_id"])
        # Use the exact job snapshot committed with the returned facility version.
        # A later read could observe a different decision and defeat the CAS guard.
        job = f["launch_snapshots"][job_id]
        decision = next(d for d in f["latest_decisions"] if d["job_id"] == job_id)
        if job["status"] not in {"placed", "waiting"}:
            raise ValueError("job already launched or completed; duplicate launch rejected")
        if decision["action"] in {"DEFER", "CHECKPOINT_AND_DEFER"}:
            return {"power_wait": True, "reason": decision["reason"]}
        if decision["action"] == "INFEASIBLE":
            raise ValueError(decision["reason"])
        from scheduler.power import utc
        chosen = job["placement"]["chosen"]
        if utc(chosen["start"] + ":00Z") > datetime.now(timezone.utc):
            return {"power_wait": True, "reason": "Waiting for the Tidewise recovery placement."}
        region = chosen["region"]
        values[":r"] = region
        update["ConditionExpression"] += " AND power_version = :v"
        values[":v"] = job["power_version"]
        check = {"ConditionCheck": {"TableName": db.table_name(), "Key": {"PK": f["PK"], "SK": "META"},
                                    "ConditionExpression": "version = :v", "ExpressionAttributeValues": {":v": f["version"]}}}
        try:
            facilities.transaction([check, {"Update": update}])
        except ClientError as exc:
            if facilities.conflict(exc):
                return {"power_wait": True, "reason": "Concurrent facility or job change; retry launch guard."}
            raise
    else:
        db.table().update_item(**{k: v for k, v in update.items() if k != "TableName"})
    seconds = float(os.environ.get("DEMO_RUN_SECONDS", "20"))
    result = run_worker(region, job_id, seconds)
    if job.get("facility_id"):
        _update_status(job_id, "running", worker_result=result, execution_status="REAL_PROXY_EXECUTED")
    else:
        _update_status(job_id, "running", worker_result=result)
    return result


def proxy_energy_kwh(cpu_s: float) -> float:
    watts = c.value("proxy_run", "max_watts_per_vcpu")
    return watts * cpu_s / 3600.0 / 1000.0


def finish(job_id: str, run: dict) -> dict:
    job = jobs.get(job_id)
    placement = job["placement"]
    chosen_fp = Footprint(**{**placement_fp(job, "chosen")})
    base_fp = Footprint(**{**placement_fp(job, "baseline")})
    modelled = receipt(chosen_fp, base_fp)
    proxy_kwh = proxy_energy_kwh(run["cpu_s"])
    proxy_scale = proxy_kwh / chosen_fp.it_kwh if chosen_fp.it_kwh else 0.0
    proxy = receipt(rescale(chosen_fp, proxy_kwh), rescale(base_fp, proxy_kwh)) if proxy_kwh > 0 else None
    item = {
        "PK": db.receipt_pk(job_id), "SK": db.META, "job_id": job_id, "final": True,
        "created_at": _now(),
        "ran_in": run.get("region"), "requested_region": run.get("requested_region"),
        "launched_via": run.get("launched_via"), "fallback_reason": run.get("fallback_reason"),
        "chosen": placement["chosen"], "baseline": placement["baseline"],
        "declared_job": {
            "gpu_hours": job["request"]["gpu_hours"], "gpu": job["request"]["gpu"],
            "energy_basis": "estimated (GPU TDP × utilisation × overhead)",
            "receipt": modelled,
        },
        "proxy_run": {
            "what": "CPU training loop standing in for the GPU job (Lambda/Fargate have no GPUs)",
            "wall_s": run.get("wall_s"), "cpu_s": run.get("cpu_s"), "epochs": run.get("epochs"),
            "final_loss": run.get("final_loss"), "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "energy_kwh": round(proxy_kwh, 9),
            "energy_basis": "measured CPU time × CCF max watts per vCPU",
            "receipt": proxy,
            "share_of_declared": round(proxy_scale, 9),
        },
    }
    db.put_item(item)
    bucket = os.environ.get("BUCKET_NAME")
    if bucket:
        boto3.client("s3", endpoint_url=db.endpoint_url()).put_object(
            Bucket=bucket, Key=f"receipts/{job_id}.json",
            Body=json.dumps(db.from_dynamo(db.to_dynamo(item)), default=str).encode(),
            ContentType="application/json")
    _update_status(job_id, "done", ran_in=run.get("region"))
    if job.get("facility_id"):
        from . import facilities
        facilities.reevaluate(job["facility_id"])
    saved = modelled["saved"]
    return {"job_id": job_id, "ran_in": run.get("region"), "saved_litres": saved["litres"],
            "saved_litres_pct": saved["litres_pct"], "saved_kg_co2": saved["kg_co2"],
            "saved_kg_co2_pct": saved["kg_co2_pct"]}


def placement_fp(job: dict, which: str) -> dict:
    """Rebuild a Footprint from the stored preview receipt (it holds the full footprints)."""
    preview = job.get("preview_receipt") or {}
    fp = preview.get(which)
    if fp is None:
        raise ValueError(f"job {job['job_id']} has no {which} footprint")
    return fp


def fail(job_id: str, error: dict | None) -> dict:
    cause = (error or {}).get("Cause") or (error or {}).get("Error") or "unknown error"
    _update_status(job_id, "failed", error=str(cause)[:500])
    return {"job_id": job_id, "status": "failed", "error": str(cause)[:500]}
