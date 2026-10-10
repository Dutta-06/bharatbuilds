import copy
from datetime import timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest
from botocore.exceptions import ClientError

from backend import db, executor, facilities as f, jobs
from backend.http import BadRequest
from scheduler.power import decide, utc
from .conftest import NOW, body, http, load_handler

TIME = NOW.replace(tzinfo=timezone.utc)


@pytest.fixture
def demo(aws):
    return f.reset_demo(TIME)


def telemetry(state, seconds=1, event_id=None):
    payload = {"power_state": state, "advance_s": seconds}
    if event_id:
        payload["event_id"] = event_id
    return f.simulation_event(f.DEMO_ID, payload)


def test_demo_lifecycle_and_units(demo):
    assert demo["facility"]["metrics"]["baseline_it_kw"] == 55
    event = telemetry("GENERATOR", event_id="outage")
    result = f.process_event(event)
    view = f.view(f.DEMO_ID)
    metrics = view["facility"]["metrics"]
    assert (metrics["baseline_it_kw"], metrics["post_decision_it_kw"], metrics["deferred_it_kw"]) == (55, 27, 28)
    assert metrics["demand_reduction_pct"] == 50.9
    actions = {d["job_id"]: d["action"] for d in result["decisions"]}
    assert actions["dg-demo-training"] == "CHECKPOINT_AND_DEFER"
    assert actions["dg-demo-etl"] == "CONTINUE"
    assert actions["dg-demo-backup"] == "DEFER"
    version = view["facility"]["version"]
    assert f.process_event(event)["duplicate"]
    assert f.read(f.DEMO_ID)["version"] == version
    f.process_event(telemetry("GENERATOR", 5400))
    assert f.read(f.DEMO_ID)["metrics"]["deferred_it_kwh"] == 42
    assert jobs.get("dg-demo-etl")["status"] == "done"
    f.process_event(telemetry("GRID_RECOVERY"))
    assert jobs.get("dg-demo-training")["status"] == "deferred"
    f.process_event(telemetry("GRID_RECOVERY", 30))
    view = f.view(f.DEMO_ID)
    assert view["facility"]["power_state"] == "GRID"
    assert jobs.get("dg-demo-training")["status"] == "running"
    assert jobs.get("dg-demo-backup")["status"] == "running"
    assert view["facility"]["fuel_estimate"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("change,status", [({"power_state": "DIESEL"}, 400), ({"facility_id": "missing"}, 404),
                                         ({"facility_id": "../x"}, 400), ({"generation": "old"}, 409)])
def test_event_validation(demo, change, status):
    event = {**telemetry("GENERATOR"), **change}
    with pytest.raises(BadRequest) as exc:
        f.process_event(event)
    assert exc.value.status == status


def test_invalid_transition_order_and_duplicate_payload(demo):
    with pytest.raises(BadRequest, match="transition"):
        f.process_event(telemetry("GRID_RECOVERY"))
    event = telemetry("GENERATOR", event_id="same")
    f.process_event(event)
    with pytest.raises(BadRequest, match="different payload"):
        f.process_event({**event, "source": "different"})
    with pytest.raises(BadRequest, match="out-of-order"):
        f.process_event({**event, "event_id": "late"})


def test_reset_is_repeatable_and_rejects_old_generation(demo):
    event = telemetry("GENERATOR")
    f.process_event(event)
    f.reset_demo(TIME)
    assert f.view(f.DEMO_ID)["facility"]["metrics"]["post_decision_it_kw"] == 55
    with pytest.raises(BadRequest, match="generation"):
        f.process_event(event)


def test_long_outage_resumes_before_deadlines(demo):
    f.process_event(telemetry("GENERATOR"))
    f.process_event(telemetry("GENERATOR", 7 * 3600))
    assert jobs.get("dg-demo-training")["status"] == "running"
    assert jobs.get("dg-demo-backup")["status"] == "running"
    assert f.read(f.DEMO_ID)["metrics"]["deadlines_feasible"]


def test_hysteresis_flicker_and_repeated_recovery(demo):
    f.process_event(telemetry("GENERATOR"))
    f.process_event(telemetry("GRID_RECOVERY"))
    f.process_event(telemetry("GRID_RECOVERY", 10))
    assert jobs.get("dg-demo-training")["status"] == "deferred"
    f.process_event(telemetry("GENERATOR"))
    f.process_event(telemetry("GRID_RECOVERY"))
    with pytest.raises(BadRequest, match="hysteresis"):
        f.process_event(telemetry("GRID", 5))
    f.process_event(telemetry("GRID_RECOVERY", 30))
    assert jobs.get("dg-demo-training")["status"] == "running"


def test_critical_deadline_capacity_overhead_dependencies(demo):
    facility = demo["facility"]
    facility["power_state"] = "GENERATOR"
    workloads = demo["workloads"]
    ds = decide(facility, workloads, TIME)
    assert all(d["action"] == "CONTINUE" for d in ds if d["job_id"] in {"dg-demo-api", "dg-demo-database", "dg-demo-auth"})
    training = next(j for j in workloads if j["job_id"] == "dg-demo-training")
    training["checkpoint_overhead_s"] = 23000
    assert next(d for d in decide(facility, workloads, TIME) if d["job_id"] == training["job_id"])["action"] == "INFEASIBLE"
    training["checkpoint_overhead_s"] = 0
    training["checkpoint_supported"] = False
    assert next(d for d in decide(facility, workloads, TIME) if d["job_id"] == training["job_id"])["action"] == "CONTINUE"
    facility["generator_capacity_kw"] = 10
    assert any(d["action"] == "INFEASIBLE" and "capacity" in d["reason"] for d in decide(facility, workloads, TIME))
    facility["generator_capacity_kw"] = 60
    training["dependencies"] = ["missing-dependency"]
    assert next(d for d in decide(facility, workloads, TIME) if d["job_id"] == training["job_id"])["action"] == "DEFER"


def test_cross_facility_isolation_and_unassociated_jobs(demo, seeded):
    original = jobs.submit({"gpu_hours": 2, "deadline_h": 24})
    f.process_event(telemetry("GENERATOR"))
    assert jobs.get(original["job_id"]) == original
    other = copy.deepcopy(f.read(f.DEMO_ID))
    other.update(PK="FACILITY#other", facility_id="other", GSI1SK="other", job_ids=[])
    db.put_item(other)
    prior = f.read("other")
    f.process_event(telemetry("GENERATOR", 60))
    assert f.read("other") == prior


def test_real_telemetry_age_and_no_shortened_safety_defaults(demo):
    facility = f.read(f.DEMO_ID)
    facility.update(simulation=False, recovery_hysteresis_s=300)
    db.put_item(facility)
    event = {"facility_id": f.DEMO_ID, "event_id": "real", "power_state": "GENERATOR", "observed_at": f.stamp(TIME + timedelta(seconds=1)), "source": "sensor"}
    with pytest.raises(BadRequest, match="stale"):
        f.process_event(event, TIME + timedelta(hours=1))
    assert not f.process_event(event, TIME + timedelta(seconds=1))["duplicate"]


def test_concurrent_duplicate_commits_once(demo, monkeypatch):
    # Moto rolls back transactions by restoring a table snapshot and is not
    # thread-safe. Serialize only its transaction implementation; caller reads
    # still race and exercise the facility/job conditional-write retry path.
    from threading import Lock
    lock = Lock()
    original = f.transaction
    def atomic_moto(ops):
        with lock:
            original(ops)
    monkeypatch.setattr(f, "transaction", atomic_moto)
    event = telemetry("GENERATOR")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: f.process_event(event), range(2)))
    assert sum(not r["duplicate"] for r in results) == 1
    assert f.read(f.DEMO_ID)["event_sequence"] == 1


def test_atomic_conflict_and_partial_failure_retry(demo, monkeypatch):
    event = telemetry("GENERATOR")
    real_transaction = f.transaction
    def failure(ops):
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "injected failure"}}, "TransactWriteItems")
    monkeypatch.setattr(f, "transaction", failure)
    with pytest.raises(ClientError):
        f.process_event(event)
    assert f.read(f.DEMO_ID)["power_state"] == "GRID"
    assert jobs.get("dg-demo-training")["status"] == "running"
    monkeypatch.setattr(f, "transaction", real_transaction)
    assert not f.process_event(event)["duplicate"]


def test_cloud_guard_and_no_duplicate_launch(demo, seeded, monkeypatch):
    site = f.read(f.DEMO_ID)
    site["grid_capacity_kw"] = 62  # Demo's six workloads otherwise exhaust grid capacity.
    db.put_item(site)
    job = jobs.submit({"gpu_hours": 2, "deadline_h": 24, "facility_id": f.DEMO_ID,
                       "estimated_power_kw": 2, "criticality": "INTERRUPTIBLE"})
    executor.load(job["job_id"])
    f.process_event(telemetry("GENERATOR"))
    calls = []
    monkeypatch.setattr(executor, "run_worker", lambda *args: calls.append(args) or {"cpu_s": 1})
    assert executor.launch(job["job_id"], "ap-south-1")["power_wait"]
    assert not calls
    f.process_event(telemetry("GRID_RECOVERY"))
    f.process_event(telemetry("GRID_RECOVERY", 30))
    executor.launch(job["job_id"], "ap-south-1")
    executor.launch(job["job_id"], "ap-south-1")
    assert len(calls) == 1


def test_cloud_running_never_checkpointed(demo, seeded):
    job = jobs.submit({"gpu_hours": 2, "deadline_h": 24, "facility_id": f.DEMO_ID, "estimated_power_kw": 2, "criticality": "CHECKPOINTABLE"})
    executor._update_status(job["job_id"], "running")
    f.process_event(telemetry("GENERATOR"))
    actual = jobs.get(job["job_id"])
    assert actual["status"] == "running" and actual["last_power_action"] == "CONTINUE"
    assert actual["execution_status"] == "ADVISORY"


def test_failed_worker_is_not_relaunched(demo, seeded, monkeypatch):
    job = jobs.submit({"gpu_hours": 2, "deadline_h": 24})
    executor.load(job["job_id"])
    def fail(*args):
        raise RuntimeError("worker result uncertain")
    monkeypatch.setattr(executor, "run_worker", fail)
    with pytest.raises(RuntimeError):
        executor.launch(job["job_id"], "ap-south-1")
    with pytest.raises(ValueError, match="duplicate"):
        executor.launch(job["job_id"], "ap-south-1")


def test_api_reads_auth_and_validation(demo, monkeypatch):
    handler = load_handler("facilities")
    assert body(handler(http(path="/facilities"), None))["facilities"]
    event = http(path="/facilities/demo-delhi-01", path_params={"id": f.DEMO_ID})
    assert handler(event, None)["statusCode"] == 200
    event["requestContext"] = {"http": {"method": "POST"}}
    event["body"] = '{"power_state":"GENERATOR"}'
    assert handler(event, None)["statusCode"] == 401
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"sub": "user"}}}
    assert handler(event, None)["statusCode"] == 403
    event["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = ["platform-leads"]
    monkeypatch.setattr(f, "publish", lambda event: {"accepted": True, "ingestion": "AWS_IOT_CORE"})
    assert handler(event, None)["statusCode"] == 202
    event["body"] = '{"power_state":"INVALID"}'
    assert handler(event, None)["statusCode"] == 400


def test_iot_handler_topic_binding(demo):
    handler = load_handler("power_event")
    with pytest.raises(ValueError, match="topic"):
        handler({**telemetry("GENERATOR"), "topic_facility": "other"}, None)
    assert not handler({**telemetry("GENERATOR"), "topic_facility": f.DEMO_ID}, None)["duplicate"]


def test_failed_resume_rolls_back_and_retries_once(demo, monkeypatch):
    f.process_event(telemetry("GENERATOR"))
    f.process_event(telemetry("GRID_RECOVERY"))
    event = telemetry("GRID_RECOVERY", 30)
    original = f.transaction
    monkeypatch.setattr(f, "transaction", lambda ops: (_ for _ in ()).throw(ClientError({"Error": {"Code": "InternalServerError"}}, "TransactWriteItems")))
    with pytest.raises(ClientError):
        f.process_event(event)
    assert jobs.get("dg-demo-training")["status"] == "deferred"
    monkeypatch.setattr(f, "transaction", original)
    f.process_event(event)
    actions = jobs.get("dg-demo-training")["power_actions"]
    assert sum(a["action"] == "RESUME" for a in actions) == 1
    f.process_event(event)
    assert jobs.get("dg-demo-training")["power_actions"] == actions


def test_facility_jobs_never_cancel_execution(demo, seeded):
    from backend import replan
    job = jobs.submit({"gpu_hours": 2, "deadline_h": 24, "facility_id": f.DEMO_ID, "estimated_power_kw": 2})
    executor.load(job["job_id"])
    class UnavailableCancellation:
        def stop_execution(self, **kwargs):
            raise AssertionError("DG must not request cancellation")
    with pytest.raises(BadRequest, match="coordinated"):
        replan.reschedule(job["job_id"], sfn=UnavailableCancellation())
    executor._update_status(job["job_id"], "done")
    f.reevaluate(f.DEMO_ID)
    assert jobs.get(job["job_id"])["status"] == "done"
    with pytest.raises(ValueError, match="duplicate"):
        executor.launch(job["job_id"], "ap-south-1")


def test_real_provision_defaults_and_private_view(aws):
    site = f.provision({"facility_id": "private-site", "generator_capacity_kw": 50, "grid_capacity_kw": 100}, TIME)
    assert site["recovery_hysteresis_s"] == 300
    assert not f.all_public()
    with pytest.raises(BadRequest) as exc:
        f.view("private-site")
    assert exc.value.status == 404
    with pytest.raises(BadRequest, match="finite"):
        f.provision({"facility_id": "unsafe-site", "generator_capacity_kw": 50, "grid_capacity_kw": 100, "recovery_hysteresis_s": 30})


def test_residency_and_max_delay_constraints(demo):
    facility = demo["facility"]
    workload = copy.deepcopy(demo["workloads"][-1])
    workload.update(execution_mode="CLOUD_PROXY", status="waiting", placement={"chosen": {"region": "ap-south-1"}})
    facility["allowed_regions"] = ["eu-north-1"]
    assert decide(facility, [workload], TIME)[0]["action"] == "INFEASIBLE"
    facility["allowed_regions"] = None
    workload["request"]["max_delay_h"] = 0
    assert decide(facility, [workload], TIME + timedelta(seconds=1))[0]["action"] == "INFEASIBLE"


def test_reset_cannot_orphan_additional_cloud_jobs(demo, seeded):
    job = jobs.submit({"gpu_hours": 2, "deadline_h": 24, "facility_id": f.DEMO_ID, "estimated_power_kw": 2})
    with pytest.raises(BadRequest, match="additional workloads"):
        f.reset_demo(TIME)
    assert job["job_id"] in f.read(f.DEMO_ID)["job_ids"]


def test_uncertain_cross_region_failure_does_not_fallback(aws, monkeypatch):
    class FailedLambda:
        def invoke(self, **kwargs):
            raise ClientError({"Error": {"Code": "ServiceException"}}, "Invoke")
    monkeypatch.setattr(executor.boto3, "client", lambda *args, **kwargs: FailedLambda())
    monkeypatch.setattr(executor, "_inline_worker", lambda: (_ for _ in ()).throw(AssertionError("unsafe fallback")))
    with pytest.raises(ClientError):
        executor.run_worker("ap-south-1", "job", 1)


def test_sensor_event_after_periodic_accounting_tick_is_accepted(demo):
    site = f.read(f.DEMO_ID)
    site["simulation"] = False
    db.put_item(site)
    f.reevaluate(f.DEMO_ID, TIME + timedelta(seconds=30))
    event = {"facility_id": f.DEMO_ID, "event_id": "delayed-sensor", "source": "sensor", "power_state": "GENERATOR", "observed_at": f.stamp(TIME + timedelta(seconds=20))}
    assert not f.process_event(event, TIME + timedelta(seconds=35))["duplicate"]
    site = f.read(f.DEMO_ID)
    assert site["last_observed_at"] == event["observed_at"]
    assert site["last_applied_at"] == f.stamp(TIME + timedelta(seconds=35))


def test_simulator_request_id_replay_returns_original_event(demo):
    request = {"power_state": "GENERATOR", "event_id": "retry-request"}
    first = f.simulation_event(f.DEMO_ID, request)
    f.process_event(first)
    repeated = f.simulation_event(f.DEMO_ID, request)
    assert repeated == first
    assert f.process_event(repeated)["duplicate"]
    with pytest.raises(BadRequest, match="different simulator"):
        f.simulation_event(f.DEMO_ID, {**request, "advance_s": 10})


def test_infeasible_work_is_not_reported_as_confirmed_environmental_savings(demo):
    f.process_event(telemetry("GENERATOR"))
    training = db.get_item(db.job_pk("dg-demo-training"), db.META)
    training["remaining_runtime_s"] = 1e6
    db.put_item(training)
    f.process_event(telemetry("GENERATOR", 1))
    training = jobs.get("dg-demo-training")
    assert training["last_power_action"] == "INFEASIBLE"
    assert training["execution_status"] == "NOT_EXECUTED"
    assert f.read(f.DEMO_ID)["metrics"]["deferred_it_kw"] == 10
    assert not f.read(f.DEMO_ID)["metrics"]["deadlines_feasible"]


def test_public_submission_cannot_overwrite_demo_or_existing_jobs(demo, seeded):
    original = jobs.get("dg-demo-training")
    with pytest.raises(BadRequest, match="already exists"):
        jobs.submit({"id": "dg-demo-training", "gpu_hours": 2, "deadline_h": 24})
    assert jobs.get("dg-demo-training") == original
    job = jobs.submit({"id": "stable-cloud-id", "gpu_hours": 2, "deadline_h": 24})
    with pytest.raises(BadRequest, match="already exists"):
        jobs.submit({"id": "stable-cloud-id", "gpu_hours": 2, "deadline_h": 24})
    assert jobs.get("stable-cloud-id") == job


def test_late_completion_never_erases_a_missed_deadline(demo):
    site = demo["facility"]
    job = copy.deepcopy(demo["workloads"][4])
    job.update(status="done", completed_at=f.stamp(TIME + timedelta(hours=2)))
    decision = decide(site, [job], TIME + timedelta(hours=2))[0]
    assert decision["action"] == "NO_ACTION"
    assert not decision["deadline_feasible"]
