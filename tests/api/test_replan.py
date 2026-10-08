import pytest

from backend import db, jobs, replan
from backend.http import BadRequest

from .conftest import NOW, body, http, load_handler

STATE_MACHINE = "arn:aws:states:ap-south-1:000000000000:stateMachine:pravaah-run"


class FakeSfn:
    def __init__(self, stop_error=None, start_error=None):
        self.calls, self.stop_error, self.start_error = [], stop_error, start_error

    def stop_execution(self, **kw):
        if self.stop_error:
            raise self.stop_error
        self.calls.append(("stop", kw["executionArn"]))

    def start_execution(self, **kw):
        if self.start_error:
            raise self.start_error
        self.calls.append(("start", kw["name"]))


@pytest.fixture
def waiting(seeded, monkeypatch):
    """A job placed, then moved to a deliberately poor plan (Mumbai at noon) so a better one exists."""
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 36, "name": "demo"}), None))
    item = db.get_item(db.job_pk(job["job_id"]), db.META)
    item["status"] = "waiting"
    item["placement"]["chosen"].update(region="ap-south-1", start="2026-10-10T12:00", end="2026-10-10T16:00")
    db.put_item(item)
    monkeypatch.setenv("RUN_STATE_MACHINE_ARN", STATE_MACHINE)     # after submit: no real run in the test
    return job["job_id"]


def test_nudge_once_per_better_plan(waiting):
    sent = []
    out = replan.nudge_all(publish=lambda subject, text: sent.append((subject, text)), app_url="https://app.example")
    assert out == {"checked": 1, "nudged": [waiting]}
    assert "better slot" in sent[0][0] and "https://app.example/#/jobs/" + waiting in sent[0][1]
    assert replan.nudge_all(publish=lambda *a: sent.append(a))["nudged"] == []   # same plan: no second email
    assert len(sent) == 1


def test_no_nudge_when_plan_is_already_best(seeded, monkeypatch):
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 36}), None))
    item = db.get_item(db.job_pk(job["job_id"]), db.META)
    item["status"] = "waiting"
    db.put_item(item)
    assert replan.nudge_all(publish=lambda *a: pytest.fail("should not email"))["nudged"] == []


def test_running_or_started_jobs_are_left_alone(waiting):
    item = db.get_item(db.job_pk(waiting), db.META)
    item["placement"]["chosen"]["start"] = "2026-10-10T06:00"       # starts this hour
    db.put_item(item)
    assert replan.nudge_all(publish=lambda *a: pytest.fail("should not email"))["nudged"] == []


def test_reschedule_stops_old_run_and_starts_new(waiting):
    sfn = FakeSfn()
    out = replan.reschedule(waiting, sfn=sfn)
    assert out["rescheduled"] and out["from"] == {"region": "ap-south-1", "start": "2026-10-10T12:00"}
    assert sfn.calls == [("stop", STATE_MACHINE.replace(":stateMachine:", ":execution:") + f":job-{waiting}"),
                         ("start", f"job-{waiting}-r1")]
    item = jobs.get(waiting)
    assert item["status"] == "placed" and item["reschedules"] == 1
    assert (item["placement"]["chosen"]["region"], item["placement"]["chosen"]["start"]) == (out["to"]["region"], out["to"]["start"])
    assert item["preview_receipt"]["saved"]["litres"] > 0
    with pytest.raises(BadRequest) as e:                              # no longer waiting: no double move
        replan.reschedule(waiting, sfn=sfn)
    assert e.value.status == 409


def test_reschedule_changes_nothing_if_old_run_cannot_be_stopped(waiting):
    before = jobs.get(waiting)
    with pytest.raises(BadRequest) as e:
        replan.reschedule(waiting, sfn=FakeSfn(stop_error=RuntimeError("AccessDenied")))
    assert e.value.status == 502
    assert jobs.get(waiting)["placement"] == before["placement"] and jobs.get(waiting)["status"] == "waiting"


def test_reschedule_when_nothing_better(seeded, monkeypatch):
    monkeypatch.delenv("RUN_STATE_MACHINE_ARN", raising=False)
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 36}), None))
    item = db.get_item(db.job_pk(job["job_id"]), db.META)
    item["status"] = "waiting"
    db.put_item(item)
    out = replan.reschedule(job["job_id"])
    assert out["rescheduled"] is False


def test_endpoint_errors(seeded):
    h = load_handler("reschedule_job")
    assert h(http(path_params={"id": "nope"}), None)["statusCode"] == 404
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 1, "deadline_h": 24}), None))
    assert h(http(path_params={"id": job["job_id"]}), None)["statusCode"] == 409   # still "placed", not waiting
