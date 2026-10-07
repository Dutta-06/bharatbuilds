import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

import pytest
import yaml

from assistant import eval as ev
from assistant import tools

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def stub_api(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), ev._Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("PRAVAAH_API_URL", f"http://127.0.0.1:{server.server_address[1]}")
    tools.CALLS.clear()
    yield
    server.shutdown()


def test_tools_against_stub(stub_api):
    s = tools.get_surface(gpu_hours=4)
    assert s["best"]["region"] == "eu-north-1"
    assert s["best_per_region"][0]["region"] == "eu-north-1"
    j = tools.submit_job(gpu_hours=8, deadline="2026-10-09T18:00Z", water_weight=1, carbon_weight=0)
    assert j["status"] == "placed" and j["chosen"]["region"] == "eu-north-1"
    r = tools.get_receipt("stub01")
    assert r["final"] is False
    assert [c["tool"] for c in tools.CALLS] == ["get_surface", "submit_job", "get_receipt"]
    assert tools.CALLS[1]["args"]["weights"] == {"water": 1, "carbon": 0}


def test_tool_errors_are_returned_not_raised(stub_api):
    assert tools._call("GET", "/nope")["status"] == 404


def test_eval_file_shape():
    spec = yaml.safe_load(ev.CASES.read_text(encoding="utf-8"))
    assert len(spec["cases"]) == 20 and spec["pass_mark"] == 16
    assert {c["expect"]["tool"] for c in spec["cases"]} == {"submit_job", "get_surface", "get_receipt", "none"}


def call(**args):
    base = {"gpu_hours": 8, "gpus": 1, "gpu": "a100", "submit_region": "ap-south-1",
            "weights": {"water": 1.0, "carbon": 0.0}, "deadline": "2026-10-09T18:00Z"}
    base.update(args)
    return [{"tool": "submit_job", "args": base}]


def test_grader():
    exp = {"tool": "submit_job", "gpu_hours": 8, "water": 1.0,
           "deadline_between": ["2026-10-09T00:00Z", "2026-10-10T00:00Z"]}
    assert ev.grade(exp, call(), NOW)[0]
    assert not ev.grade(exp, call(gpu_hours=6), NOW)[0]
    assert not ev.grade(exp, call(deadline="2026-10-11T00:00Z"), NOW)[0]
    assert ev.grade(exp, call(deadline=None, deadline_h=40), NOW)[0]          # Fri 04:00Z
    assert not ev.grade({"tool": "none"}, call(), NOW)[0]
    assert ev.grade({"tool": "none"}, [], NOW)[0]
    assert not ev.grade({"tool": "get_surface", "no_submit": True},
                        [{"tool": "get_surface", "args": {}}] + call(), NOW)[0]
    india = {"tool": "submit_job", "india_only": True}
    assert ev.grade(india, call(allowed_regions=["ap-south-1", "ap-south-2"]), NOW)[0]
    assert ev.grade(india, call(data_residency=True), NOW)[0]
    assert not ev.grade(india, call(allowed_regions=["eu-north-1"]), NOW)[0]
    assert ev.grade({"tool": "get_receipt", "job_id": "abc123"},
                    [{"tool": "get_receipt", "args": {"job_id": "abc123"}}], NOW)[0]


def test_chat_handler_validates_input(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("chat", Path(__file__).resolve().parents[2] / "functions/chat/app.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.handler({"body": json.dumps({"message": ""})}, None)["statusCode"] == 400
    monkeypatch.setattr(m.agent, "ask", lambda msg: tools.CALLS.append({"tool": "x", "args": {}}) or "ok")
    out = m.handler({"body": json.dumps({"message": "hi"})}, None)
    assert out["statusCode"] == 200 and json.loads(out["body"])["tool_calls"] == [{"tool": "x", "args": {}}]
