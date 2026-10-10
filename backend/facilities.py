"""Facility telemetry, transactional state and modeled execution in Tidewise's table."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from backend import db, jobs
from model.generator import fuel_rate
from backend.http import BadRequest
from scheduler.power import CLASSES, TERMINAL, decide, utc

DEMO_ID = "demo-delhi-01"
DECISION_TTL = timedelta(days=7)
STATES = {"GRID", "BATTERY_TRANSITION", "GENERATOR", "GRID_RECOVERY"}
TRANSITIONS = {"GRID": {"GRID", "BATTERY_TRANSITION", "GENERATOR"},
               "BATTERY_TRANSITION": {"BATTERY_TRANSITION", "GENERATOR", "GRID_RECOVERY"},
               "GENERATOR": {"GENERATOR", "GRID_RECOVERY"},
               "GRID_RECOVERY": {"GRID_RECOVERY", "GENERATOR", "GRID"}}


def stamp(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise BadRequest("invalid facility or event identifier")
    return value


def number(value, name, minimum=0, maximum=1e7):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise BadRequest(f"{name} must be a finite number between {minimum} and {maximum}")
    return value


def read(facility_id):
    item = db.table().get_item(Key={"PK": f"FACILITY#{identifier(facility_id)}", "SK": "META"}, ConsistentRead=True).get("Item")
    if not item:
        raise BadRequest("unknown facility", 404)
    return db.from_dynamo(item)


def workload_items(f):
    result = []
    for jid in f["job_ids"]:
        item = db.table().get_item(Key={"PK": db.job_pk(jid), "SK": db.META}, ConsistentRead=True).get("Item")
        if not item:
            raise BadRequest("facility references a missing workload", 409)
        j = db.from_dynamo(item)
        if j.get("facility_id") != f["facility_id"]:
            raise BadRequest("facility workload association is inconsistent", 409)
        result.append(j)
    return result


def all_public():
    rows = db.query(Key("GSI1PK").eq("FACILITIES"), index="GSI1")
    return [jobs.public(f) for f in rows if f.get("public_demo")]


def view(fid):
    f = read(fid)
    if not f.get("public_demo"):
        raise BadRequest("facility is not public", 404)
    return {"facility": jobs.public(f), "workloads": [jobs.public(j) for j in workload_items(f)]}


def history(fid):
    f = read(fid)
    if not f.get("public_demo"):
        raise BadRequest("facility is not public", 404)
    return db.query(Key("PK").eq(f["PK"]) & Key("SK").begins_with("DECISION#"), forward=False, limit=30)


def put_tx(item, condition=None, values=None):
    put = {"TableName": db.table_name(), "Item": db.to_dynamo(item)}
    if condition:
        put["ConditionExpression"] = condition
    if values:
        put["ExpressionAttributeValues"] = db.to_dynamo(values)
    return {"Put": put}


def transaction(operations):
    # Resource client applies DynamoDB's Python/Decimal conversion to nested transactions.
    db.table().meta.client.transact_write_items(TransactItems=operations)


def conflict(exc):
    return exc.response["Error"]["Code"] in {"TransactionCanceledException", "ConditionalCheckFailedException", "TransactionConflictException"}


def metadata(body, job):
    """Optional association; existing jobs without it are unchanged."""
    if "facility_id" not in body:
        return {}
    f = read(body["facility_id"])
    category = body.get("criticality", "DEADLINE")
    if not isinstance(category, str) or category not in CLASSES:
        raise BadRequest("invalid criticality")
    # Public /jobs may associate a real proxy, but cannot impersonate the simulation adapter.
    if body.get("execution_mode", "CLOUD_PROXY") != "CLOUD_PROXY":
        raise BadRequest("simulated workloads are provisioned only by the authenticated demo reset")
    if not isinstance(body.get("checkpoint_supported", False), bool):
        raise BadRequest("checkpoint_supported must be boolean")
    dependencies = body.get("dependencies", [])
    if not isinstance(dependencies, list) or any(not isinstance(d, str) or d not in f["job_ids"] or d == job.id for d in dependencies):
        raise BadRequest("dependencies must reference existing workloads at the same facility")
    return {"facility_id": f["facility_id"], "criticality": category,
            "workload_type": str(body.get("workload_type", "AI"))[:80],
            "execution_mode": "CLOUD_PROXY", "checkpoint_supported": False,
            "interruptibility": "NON_PREEMPTIBLE", "preemption_policy": "WAITING_ONLY",
            "estimated_power_kw": number(body.get("estimated_power_kw"), "estimated_power_kw", 0.001),
            "remaining_runtime_s": job.duration_h * 3600,
            "checkpoint_overhead_s": number(body.get("checkpoint_overhead_s", 0), "checkpoint_overhead_s"),
            "resume_overhead_s": number(body.get("resume_overhead_s", 0), "resume_overhead_s"),
            "dependencies": dependencies, "power_version": 0}


def register(item):
    f = read(item["facility_id"])
    if len(f["job_ids"]) >= 20:
        raise BadRequest("facility MVP limit is 20 workloads", 409)
    previous = f["version"]
    f["job_ids"] = f["job_ids"] + [item["job_id"]]
    f["version"] += 1
    try:
        transaction([put_tx(f, "version = :v", {":v": previous}),
                     put_tx(item, "attribute_not_exists(PK)")])
    except ClientError as exc:
        if conflict(exc):
            raise BadRequest("facility or job changed concurrently; retry submission", 409) from exc
        raise
    reevaluate(f["facility_id"])


def provision(config, now=None):
    """IAM-authenticated CLI/backend provisioning, never a public HTTP mutation."""
    fid = identifier(config.get("facility_id"))
    now = now or datetime.now(timezone.utc)
    simulation = config.get("simulation", False)
    if not isinstance(simulation, bool):
        raise BadRequest("simulation must be boolean")
    item = {"PK": f"FACILITY#{fid}", "SK": "META", "GSI1PK": "FACILITIES", "GSI1SK": fid,
            "facility_id": fid, "display_name": str(config.get("display_name", fid))[:100],
            "facility_type": str(config.get("facility_type", "COMPUTE_SITE"))[:80],
            "simulation": simulation, "public_demo": False, "power_state": "GRID",
            "state_changed_at": stamp(now), "last_observed_at": stamp(now), "accounted_at": stamp(now),
            "simulation_time": stamp(now), "version": 1, "generation": uuid.uuid4().hex,
            "event_sequence": 0, "job_ids": [], "deferred_it_kwh": 0, "reduced_demand_s": 0,
            "generator_capacity_kw": number(config.get("generator_capacity_kw"), "generator_capacity_kw", 0.001),
            "grid_capacity_kw": number(config.get("grid_capacity_kw"), "grid_capacity_kw", 0.001),
            "base_load_kw": number(config.get("base_load_kw", 0), "base_load_kw"),
            "reevaluation_s": number(config.get("reevaluation_s", 1800), "reevaluation_s", 60, 3600),
            "recovery_hysteresis_s": number(config.get("recovery_hysteresis_s", 300), "recovery_hysteresis_s", 300 if not simulation else 1, 3600),
            "telemetry_max_age_s": number(config.get("telemetry_max_age_s", 300), "telemetry_max_age_s", 1, 3600),
            "allowed_regions": config.get("allowed_regions"), "fuel_curve": config.get("fuel_curve")}
    try:
        transaction([put_tx(item, "attribute_not_exists(PK)")])
    except ClientError as exc:
        if conflict(exc):
            raise BadRequest("facility already exists; provisioning never overwrites it", 409) from exc
        raise
    return jobs.public(item)


def reset_demo(now=None):
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    try:
        old = read(DEMO_ID)
    except BadRequest as exc:
        if exc.status != 404:
            raise
        old = None
    if old and not old.get("simulation"):
        raise BadRequest("refusing to reset a real facility", 409)
    demo_jobs = {f"dg-demo-{suffix}" for suffix in ("api", "database", "auth", "training", "etl", "backup")}
    if old and set(old["job_ids"]) - demo_jobs:
        raise BadRequest("refusing reset: facility has additional workloads; provision a separate site for cloud integration", 409)
    version = old["version"] + 1 if old else 1
    f = {"PK": f"FACILITY#{DEMO_ID}", "SK": "META", "GSI1PK": "FACILITIES", "GSI1SK": DEMO_ID,
         "facility_id": DEMO_ID, "display_name": "Delhi demonstration facility", "facility_type": "SIMULATED_COMPUTE_SITE",
         "simulation": True, "public_demo": True, "power_state": "GRID", "state_changed_at": stamp(now),
         "last_observed_at": stamp(now), "simulation_time": stamp(now), "accounted_at": stamp(now),
         "version": version, "generation": uuid.uuid4().hex, "event_sequence": 0,
         "generator_capacity_kw": 60, "grid_capacity_kw": 60, "base_load_kw": 5,
         "reevaluation_s": 1800, "recovery_hysteresis_s": 30, "telemetry_max_age_s": 300,
         "deferred_it_kwh": 0, "reduced_demand_s": 0, "job_ids": [],
         "fuel_estimate": {"status": "UNAVAILABLE", "reason": "No sourced manufacturer fuel curve configured."}}
    specs = [("api", "API", 7, None, None, "CRITICAL"),
             ("database", "Database", 8, None, None, "CRITICAL"),
             ("auth", "Authentication", 4, None, None, "CRITICAL"),
             ("training", "ML Training", 18, 14400, 36000, "CHECKPOINTABLE"),
             ("etl", "ETL", 8, 2700, 3600, "DEADLINE"),
             ("backup", "Backup", 10, 7200, 28800, "INTERRUPTIBLE")]
    ops = [put_tx(f, "version = :v", {":v": old["version"]}) if old else put_tx(f, "attribute_not_exists(PK)")]
    for suffix, name, power, runtime, deadline_s, category in specs:
        jid = f"dg-demo-{suffix}"
        f["job_ids"].append(jid)
        j = {"PK": db.job_pk(jid), "SK": "META", "GSI1PK": "JOBS", "GSI1SK": f"{stamp(now)}#{jid}",
             "job_id": jid, "name": name, "status": "running", "submitted_at": stamp(now),
             "facility_id": DEMO_ID, "criticality": category, "execution_mode": "SIMULATED_FACILITY",
             "checkpoint_supported": category == "CHECKPOINTABLE", "checkpoint_overhead_s": 300 if category == "CHECKPOINTABLE" else 0,
             "resume_overhead_s": 300 if category == "CHECKPOINTABLE" else 0,
             "estimated_power_kw": power, "remaining_runtime_s": runtime, "initial_runtime_s": runtime,
             "request": {"deadline": stamp(now + timedelta(seconds=deadline_s)) if deadline_s else None},
             "placement": {"chosen": None, "reason": "SIMULATED facility adapter; no AWS worker launched."},
             "power_version": version, "dependencies": [], "last_power_action": "CONTINUE", "execution_status": "SIMULATED"}
        existing = db.get_item(j["PK"], "META")
        if existing and existing.get("execution_mode") != "SIMULATED_FACILITY":
            raise BadRequest("demo job identity collision", 409)
        ops.append(put_tx(j, "power_version = :v", {":v": existing["power_version"]}) if existing else put_tx(j, "attribute_not_exists(PK)"))
    # Rebuild first operation because job_ids were populated after its conversion.
    ops[0] = put_tx(f, "version = :v", {":v": old["version"]}) if old else put_tx(f, "attribute_not_exists(PK)")
    try:
        transaction(ops)
    except ClientError as exc:
        if conflict(exc):
            raise BadRequest("demo changed concurrently; retry reset", 409) from exc
        raise
    reevaluate(DEMO_ID, now)
    return view(DEMO_ID)


def apply_decisions(f, workloads, now):
    if f["power_state"] == "GRID_RECOVERY" and (now - utc(f["state_changed_at"])).total_seconds() >= f["recovery_hysteresis_s"]:
        recovery_replan(workloads, now)
    decisions = decide(f, workloads, now)
    by_id = {j["job_id"]: j for j in workloads}
    for d in decisions:
        j = by_id[d["job_id"]]
        previous_action = j.get("last_power_action")
        if d["action"] != "NO_ACTION":
            j["last_power_action"] = d["action"]
            j["deferral_reason"] = d["reason"]
            if j["execution_mode"] == "SIMULATED_FACILITY":
                if d["action"] in {"DEFER", "CHECKPOINT_AND_DEFER"}:
                    if j["status"] != "deferred" and d["action"] == "CHECKPOINT_AND_DEFER":
                        j["remaining_runtime_s"] += j["checkpoint_overhead_s"] + j["resume_overhead_s"]
                        j["checkpoint_overhead_s"] = 0
                        j["resume_overhead_s"] = 0
                    j["status"] = "deferred"
                elif d["action"] in {"CONTINUE", "RESUME"}:
                    j["status"] = "running"
                    if d["action"] == "RESUME":
                        j["resumed_at"] = stamp(now)
                # INFEASIBLE is a decision, not a claim that a running process stopped.
                d["execution_status"] = "NOT_EXECUTED" if d["action"] == "INFEASIBLE" else "SIMULATED_CONFIRMED"
            else:
                j["power_hold"] = d["action"] in {"DEFER", "CHECKPOINT_AND_DEFER", "INFEASIBLE"}
                d["execution_status"] = "LAUNCH_GUARD_ACTIVE" if j["status"] in {"waiting", "placed"} else "ADVISORY"
            j["execution_status"] = d["execution_status"]
        else:
            j["last_power_action"] = "NO_ACTION"
            j["execution_status"] = "SIMULATED_COMPLETE" if j["execution_mode"] == "SIMULATED_FACILITY" else "COMPLETE"
        if previous_action != d["action"]:
            record = {"at": stamp(now), "action": d["action"], "reason": d["reason"], "execution_status": d["execution_status"], "deadline_feasible": d["deadline_feasible"]}
            j["power_actions"] = (j.get("power_actions", []) + [record])[-20:]
        j["power_version"] = j.get("power_version", 0) + 1
    f["latest_decisions"] = decisions
    active = [j for j in workloads if j["status"] not in TERMINAL]
    protected = {d["job_id"] for d in decisions if d["action"] == "CONTINUE" and d["deadline_feasible"]}
    baseline = sum(j["estimated_power_kw"] for j in active)
    deferred = sum(j["estimated_power_kw"] for j in active if demand_deferred(j))
    f["metrics"] = {"basis": "SIMULATED" if f["simulation"] else "MODELED",
                    "baseline_it_kw": baseline, "post_decision_it_kw": baseline - deferred, "deferred_it_kw": deferred,
                    "demand_reduction_pct": round(100 * deferred / baseline, 1) if baseline else 0,
                    "deferred_it_kwh": round(f["deferred_it_kwh"], 6), "reduced_demand_s": f["reduced_demand_s"],
                    "critical_jobs_preserved": sum(j["criticality"] == "CRITICAL" and j["status"] == "running" and j["job_id"] in protected for j in active),
                    "workloads_deferred": sum(demand_deferred(j) for j in active),
                    "deadlines_feasible": all(d["deadline_feasible"] for d in decisions),
                    "note": "Deferred IT electricity demand is shifted computing, not eliminated work, generator output, diesel fuel or pollutant savings."}
    f["fuel_estimate"] = fuel_rate(f.get("fuel_curve"), baseline - deferred + f["base_load_kw"], f["generator_capacity_kw"])
    f["recovery_status"] = "WAITING_FOR_STABLE_GRID" if f["power_state"] == "GRID_RECOVERY" else f["power_state"]
    if f["power_state"] == "GRID_RECOVERY" and (now - utc(f["state_changed_at"])).total_seconds() >= f["recovery_hysteresis_s"]:
        f["power_state"] = "GRID"
        f["state_changed_at"] = stamp(now)
        f["recovery_status"] = "CAPACITY_QUEUE" if any(demand_deferred(j) for j in active) else "COMPLETE"


def demand_deferred(job):
    if job.get("last_power_action") not in {"DEFER", "CHECKPOINT_AND_DEFER"}:
        return False
    return job["status"] == "deferred" or (job.get("execution_mode") == "CLOUD_PROXY" and
            job["status"] in {"placed", "waiting"} and job.get("power_hold") and
            job.get("last_power_action") in {"DEFER", "CHECKPOINT_AND_DEFER"})


def recovery_replan(workloads, now):
    """Use Tidewise forecasts for waiting cloud jobs; retain the same execution.

    The launch guard reads this placement afresh, so no cancel/restart is needed.
    Simulated local compute has no AWS-region footprint and is never relocated.
    """
    from backend import forecasts, replan
    from model.cost import receipt
    from scheduler.greedy import schedule
    cloud = [j for j in workloads if j["execution_mode"] == "CLOUD_PROXY" and j["status"] in {"placed", "waiting"}]
    if not cloud:
        return
    instant = now.replace(tzinfo=None)
    surface, _ = forecasts.surface(start=instant.replace(minute=0, second=0, microsecond=0))
    for j in cloud:
        model_job = replan._job_from_item(j, instant)
        plan = schedule(model_job, surface)
        if not plan.feasible:
            j["recovery_plan_error"] = plan.reason
            j["recovery_plan_status"] = "INFEASIBLE"
            continue
        j.pop("recovery_plan_error", None)
        j["placement"] = plan.as_dict(submit_time=instant)
        j["preview_receipt"] = receipt(plan.chosen.footprint, plan.baseline.footprint) if plan.baseline else None
        j["recovery_plan_status"] = "REPLANNED_WITH_TIDEWISE_FORECASTS"


def evolve(f, workloads, target):
    """Integrate at completion, deadline and hysteresis boundaries, never one huge jump."""
    current = utc(f["accounted_at"])
    if target < current:
        raise BadRequest("event precedes already accounted state", 409)
    while current < target:
        candidates = [target, current + timedelta(seconds=f["reevaluation_s"])]
        if f["power_state"] == "GRID_RECOVERY":
            ready = utc(f["state_changed_at"]) + timedelta(seconds=f["recovery_hysteresis_s"])
            if ready > current:
                candidates.append(ready)
        for j in workloads:
            if j["execution_mode"] != "SIMULATED_FACILITY" or j["status"] in TERMINAL:
                continue
            if j["status"] == "running" and j["remaining_runtime_s"] is not None:
                candidates.append(current + timedelta(seconds=max(0.000001, j["remaining_runtime_s"])))
            if j["status"] == "deferred" and j["request"].get("deadline"):
                boundary = utc(j["request"]["deadline"]) - timedelta(seconds=j["remaining_runtime_s"] + j.get("resume_overhead_s", 0) + j.get("checkpoint_overhead_s", 0) + f["reevaluation_s"])
                if boundary > current:
                    candidates.append(boundary)
        following = min(candidates)
        seconds = (following - current).total_seconds()
        if f["power_state"] == "GENERATOR":
            deferred = sum(j["estimated_power_kw"] for j in workloads if demand_deferred(j))
            f["deferred_it_kwh"] += deferred * seconds / 3600
            if deferred:
                f["reduced_demand_s"] += seconds
        for j in workloads:
            if j["execution_mode"] == "SIMULATED_FACILITY" and j["status"] == "running" and j["remaining_runtime_s"] is not None:
                j["remaining_runtime_s"] = max(0, j["remaining_runtime_s"] - seconds)
                if j["remaining_runtime_s"] == 0:
                    j["status"] = "done"
                    j["completed_at"] = stamp(following)
        current = following
        apply_decisions(f, workloads, current)
    f["accounted_at"] = stamp(target)


def process_event(event, received_at=None):
    """One atomic commit: facility CAS + job CAS + durable event ID + decisions."""
    fid = identifier(event.get("facility_id"))
    eid = identifier(event.get("event_id"))
    state = event.get("power_state")
    if not isinstance(state, str) or state not in STATES:
        raise BadRequest("invalid power_state")
    try:
        observed = utc(event.get("observed_at", ""))
    except (ValueError, AttributeError, TypeError):
        raise BadRequest("observed_at must be an ISO UTC timestamp") from None
    fingerprint = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    for attempt in range(4):
        state = event["power_state"]
        f = read(fid)
        event_key = f"EVENT#{f['generation']}#{eid}"
        prior = db.table().get_item(Key={"PK": f["PK"], "SK": event_key}, ConsistentRead=True).get("Item")
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise BadRequest("event ID reused with different payload", 409)
            return {"duplicate": True, "facility_id": fid, "version": int(prior["version"])}
        if f["simulation"] and event.get("generation") != f["generation"]:
            raise BadRequest("simulation generation changed; reload after reset", 409)
        if event.get("source") == "simulator" and not f["simulation"]:
            raise BadRequest("simulator cannot mutate a real facility", 403)
        clock = received_at or datetime.now(timezone.utc)
        if not f["simulation"] and (observed > clock or (clock - observed).total_seconds() > f["telemetry_max_age_s"]):
            raise BadRequest("stale or future telemetry", 409)
        if observed <= utc(f["last_observed_at"]):
            raise BadRequest("out-of-order event; observed_at must increase", 409)
        if state not in TRANSITIONS[f["power_state"]]:
            raise BadRequest("invalid power-state transition", 409)
        if state == "GRID" and f["power_state"] == "GRID_RECOVERY" and (observed - utc(f["state_changed_at"])).total_seconds() < f["recovery_hysteresis_s"]:
            raise BadRequest("grid recovery hysteresis has not elapsed", 409)
        originals = workload_items(f)
        workloads = copy.deepcopy(originals)
        version = f["version"]
        previous_state = f["power_state"]
        # Real sensors can arrive after a periodic accounting tick. Apply at
        # receipt time without rewriting already-accounted intervals, while
        # observation time remains the strict telemetry ordering key.
        applied_at = observed if f["simulation"] else max(clock, utc(f["accounted_at"]))
        evolve(f, workloads, applied_at)
        if previous_state == "GRID_RECOVERY" and state == "GRID_RECOVERY" and f["power_state"] == "GRID":
            state = "GRID"  # Repeated recovery signals must not restart hysteresis.
        if f["power_state"] != state:
            f["state_changed_at"] = stamp(observed)
        f.update(power_state=state, last_observed_at=stamp(observed), event_sequence=f["event_sequence"] + 1,
                 version=version + 1, last_event_id=eid)
        if f["simulation"]:
            f["simulation_time"] = stamp(observed)
        f["last_applied_at"] = stamp(applied_at)
        apply_decisions(f, workloads, applied_at)
        audit = {"PK": f["PK"], "SK": event_key, "fingerprint": fingerprint, "event": event, "version": f["version"]}
        ops = commit_operations(f, originals, workloads, version) + [put_tx(audit, "attribute_not_exists(PK)")]
        try:
            transaction(ops)
            return {"duplicate": False, "facility_id": fid, "version": f["version"], "decisions": f["latest_decisions"]}
        except ClientError as exc:
            if not conflict(exc):
                raise
            if attempt == 3:
                raise BadRequest("concurrent facility change; retry same event", 409) from exc


def commit_operations(f, originals, workloads, version):
    ops = [put_tx(f, "version = :v", {":v": version})]
    for before, after in zip(originals, workloads):
        ops.append(put_tx(after, "power_version = :v AND #s = :s", {":v": before.get("power_version", 0), ":s": before["status"]}))
        ops[-1]["Put"]["ExpressionAttributeNames"] = {"#s": "status"}
    # One decision row per commit (about one a minute while the facility is monitored): expire them.
    expires = int((datetime.now(timezone.utc) + DECISION_TTL).timestamp())
    ops.append(put_tx({"PK": f["PK"], "SK": f"DECISION#{f['version']:012d}", "at": f["accounted_at"], "expires_at": expires,
                       "power_state": f["power_state"], "decisions": f["latest_decisions"], "metrics": f["metrics"]}, "attribute_not_exists(PK)"))
    return ops


def reevaluate(fid, now=None):
    for attempt in range(4):
        f = read(fid)
        target = now or (utc(f["simulation_time"]) if f["simulation"] else datetime.now(timezone.utc))
        before = workload_items(f)
        after = copy.deepcopy(before)
        version = f["version"]
        evolve(f, after, target)
        f["version"] += 1
        apply_decisions(f, after, target)
        try:
            transaction(commit_operations(f, before, after, version))
            return {**f, "launch_snapshots": {j["job_id"]: jobs.public(j) for j in after}}
        except ClientError as exc:
            if not conflict(exc):
                raise
            if attempt == 3:
                raise BadRequest("concurrent reevaluation; retry", 409) from exc


def simulation_event(fid, body):
    f = read(fid)
    if not f["simulation"]:
        raise BadRequest("only simulated facilities accept demo controls", 403)
    seconds = number(body.get("advance_s", 1), "advance_s", 1, 86400)
    eid = identifier(body.get("event_id", uuid.uuid4().hex))
    request = {"power_state": body.get("power_state", "CURRENT"), "advance_s": seconds}
    prior = db.table().get_item(Key={"PK": f["PK"], "SK": f"EVENT#{f['generation']}#{eid}"}, ConsistentRead=True).get("Item")
    if prior:
        prior = db.from_dynamo(prior)
        if prior["event"].get("simulation_request") != request:
            raise BadRequest("event ID reused with different simulator request", 409)
        return prior["event"]
    state = body.get("power_state", f["power_state"])
    if not isinstance(state, str) or state not in STATES:
        raise BadRequest("invalid power_state")
    if state not in TRANSITIONS[f["power_state"]]:
        raise BadRequest("invalid power-state transition", 409)
    if state == "GRID" and f["power_state"] == "GRID_RECOVERY" and (utc(f["simulation_time"]) + timedelta(seconds=seconds) - utc(f["state_changed_at"])).total_seconds() < f["recovery_hysteresis_s"]:
        raise BadRequest("grid recovery hysteresis has not elapsed", 409)
    return {"facility_id": fid, "event_id": eid, "simulation_request": request,
            "observed_at": stamp(utc(f["simulation_time"]) + timedelta(seconds=seconds)),
            "power_state": state, "source": "simulator", "generation": f["generation"]}


def publish(event):
    # ATS endpoint discovery is a control-plane call; credentials stay server-side.
    endpoint = boto3.client("iot").describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    boto3.client("iot-data", endpoint_url=f"https://{endpoint}").publish(
        topic=f"tidewise/facilities/{event['facility_id']}/power", qos=1, payload=json.dumps(event).encode())
    return {"accepted": True, "event_id": event["event_id"], "ingestion": "AWS_IOT_CORE", "status": "PENDING"}
