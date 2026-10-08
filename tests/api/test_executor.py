import json
import re
from pathlib import Path

import pytest

from backend import db, executor, jobs

from .conftest import ROOT, load_handler


@pytest.fixture
def placed(seeded, monkeypatch):
    monkeypatch.setenv("WORKER_MODE", "inline")
    monkeypatch.setenv("DEMO_RUN_SECONDS", "1")
    return jobs.submit({"gpu_hours": 2, "deadline_h": 24, "submit_region": "ap-south-1"})


def test_full_run_writes_honest_receipt(placed):
    h = load_handler("executor")
    loaded = h({"action": "load", "job_id": placed["job_id"]}, None)
    # the run state machine branches on this value (IsPlaced: status == "waiting")
    assert loaded["status"] == "waiting" and loaded["wait_until"].endswith(":00Z")
    assert jobs.get(placed["job_id"])["status"] == "waiting"

    run = h({"action": "launch", "job_id": placed["job_id"], "region": loaded["region"]}, None)
    assert run["launched_via"] == "inline-fallback"
    assert run["requested_region"] == loaded["region"]
    assert run["cpu_s"] > 0 and run["epochs"] >= 1

    summary = h({"action": "finish", "job_id": placed["job_id"], "run": run}, None)
    assert summary["saved_litres"] > 0

    r = jobs.get_receipt(placed["job_id"])
    assert r["final"] is True
    assert r["launched_via"] == "inline-fallback" and r["requested_region"] == loaded["region"]
    assert r["declared_job"]["receipt"]["energy_basis"] == "estimated"
    assert r["proxy_run"]["receipt"]["energy_basis"] == "measured"
    assert "no GPUs" in r["proxy_run"]["what"]
    assert jobs.get(placed["job_id"])["status"] == "done"


def test_fail_marks_job(placed):
    out = load_handler("executor")({"action": "fail", "job_id": placed["job_id"],
                                    "error": {"Error": "X", "Cause": "boom"}}, None)
    assert out["status"] == "failed"
    job = jobs.get(placed["job_id"])
    assert job["status"] == "failed" and job["error"] == "boom"


def test_load_infeasible_job(seeded):
    job = jobs.submit({"gpu_hours": 10, "deadline_h": 2})
    out = executor.load(job["job_id"])
    assert out["status"] == "infeasible" and "wait_until" not in out


def test_unknown_action(placed):
    with pytest.raises(ValueError):
        load_handler("executor")({"action": "dance", "job_id": placed["job_id"]}, None)


def test_worker_handler_bounds_and_reports():
    out = load_handler("worker")({"job_id": "x", "seconds": 0.1}, None)
    assert out["wall_s"] >= 1.0  # minimum 1 s
    assert out["final_loss"] < 0.7


def test_store_forecast_emits_emf_metric(aws, frozen, capsys):
    from backend import forecasts
    rows = forecasts.collect("eu-north-1", offline=True)
    load_handler("store_forecast")({"region": "eu-north-1", "rows": rows}, None)
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["RowsWritten"] == 48 and line["ModelledCarbonHours"] == 48
    assert line["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "Pravaah"


# --- state machine definitions ---------------------------------------------------

SUBS = {"FetchForecastArn": "arn:aws:lambda:ap-south-1:000000000000:function:f",
        "StoreForecastArn": "arn:aws:lambda:ap-south-1:000000000000:function:s",
        "PredictArn": "arn:aws:lambda:ap-south-1:000000000000:function:p",
        "PublishSurfaceArn": "arn:aws:lambda:ap-south-1:000000000000:function:ps",
        "NudgeArn": "arn:aws:lambda:ap-south-1:000000000000:function:n",
        "ExecutorArn": "arn:aws:lambda:ap-south-1:000000000000:function:e",
        "TopicArn": "arn:aws:sns:ap-south-1:000000000000:t",
        "RegionList": '["ap-south-1","eu-north-1"]'}


def definition(name: str) -> dict:
    text = (ROOT / "statemachines" / f"{name}.asl.json").read_text()
    for k, v in SUBS.items():
        text = text.replace("${" + k + "}", v)
    assert "${" not in text, "unsubstituted placeholder"
    return json.loads(text)


def all_states(d: dict) -> dict:
    out = dict(d["States"])
    for s in d["States"].values():
        if s["Type"] == "Map":
            out.update(all_states(s.get("Iterator") or s["ItemProcessor"]))
    return out


@pytest.mark.parametrize("name", ["forecast", "run"])
def test_state_machine_references_resolve(name):
    d = definition(name)
    states = all_states(d)
    assert d["StartAt"] in states
    for sname, s in states.items():
        targets = [s.get("Next"), s.get("Default")] + [c["Next"] for c in s.get("Choices", [])] \
            + [c["Next"] for c in s.get("Catch", [])]
        for t in filter(None, targets):
            assert t in states, f"{name}: {sname} -> {t} missing"
        assert s.get("End") or s["Type"] in ("Succeed", "Fail", "Choice") or s.get("Next"), sname


def test_template_substitutions_match_definitions():
    import yaml

    class L(yaml.SafeLoader):
        pass

    L.add_multi_constructor("!", lambda loader, suffix, node: None)
    t = yaml.load((ROOT / "template.yaml").read_text(), Loader=L)
    for logical, file in (("ForecastStateMachine", "forecast"), ("RunStateMachine", "run")):
        used = set(re.findall(r"\$\{(\w+)\}", (ROOT / "statemachines" / f"{file}.asl.json").read_text()))
        given = set(t["Resources"][logical]["Properties"]["DefinitionSubstitutions"])
        assert used == given, (logical, used ^ given)


def test_default_region_list_matches_config():
    import yaml
    from model import regions

    class L(yaml.SafeLoader):
        pass

    L.add_multi_constructor("!", lambda loader, suffix, node: None)
    t = yaml.load((ROOT / "template.yaml").read_text(), Loader=L)
    listed = json.loads(t["Resources"]["ForecastStateMachine"]["Properties"]["DefinitionSubstitutions"]["RegionList"])
    assert sorted(listed) == sorted(regions.load())
