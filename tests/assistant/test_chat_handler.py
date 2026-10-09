import json
import time

from assistant import agent, tools

from tests.api.conftest import body, http, load_handler


def call(handler, message="hi"):
    return handler(http(body={"message": message}), None)


def test_answers_normally(monkeypatch):
    handler = load_handler("chat")
    monkeypatch.setattr(agent, "ask", lambda m: "eu-north-1")
    out = call(handler)
    assert out["statusCode"] == 200 and body(out)["reply"] == "eu-north-1"


def test_slow_model_gets_a_clear_504_not_a_gateway_error(monkeypatch):
    handler = load_handler("chat")
    monkeypatch.setenv("CHAT_BUDGET_S", "0.2")
    monkeypatch.setattr(agent, "ask", lambda m: time.sleep(1.5))
    out = call(handler)
    assert out["statusCode"] == 504 and "took too long" in body(out)["error"] and "Submit page" in body(out)["error"]


def test_timeout_after_a_submit_warns_about_the_queue(monkeypatch):
    handler = load_handler("chat")
    monkeypatch.setenv("CHAT_BUDGET_S", "0.2")

    def slow(message):
        tools.CALLS.append({"tool": "submit_job", "args": {}})
        time.sleep(1.5)
    monkeypatch.setattr(agent, "ask", slow)
    assert "check the Queue" in body(call(handler))["error"]


def test_provider_failure_is_a_friendly_503(monkeypatch):
    handler = load_handler("chat")

    def boom(message):
        raise RuntimeError("Error code: 404 - model is unavailable for free")
    monkeypatch.setattr(agent, "ask", boom)
    out = call(handler)
    assert out["statusCode"] == 503 and "unavailable" in body(out)["error"] and "404" not in out["body"]


def test_bad_input_still_400():
    assert call(load_handler("chat"), "")["statusCode"] == 400


def test_late_tool_calls_after_a_timeout_do_nothing(monkeypatch):
    """The timed-out model thread keeps running; when it finally calls submit_job it must not submit."""
    handler = load_handler("chat")
    monkeypatch.setenv("CHAT_BUDGET_S", "0.2")
    results = []

    def slow_then_submit(message):
        time.sleep(0.8)
        results.append(tools.submit_job(gpu_hours=1, deadline_h=24))
    monkeypatch.setattr(agent, "ask", slow_then_submit)
    assert call(handler)["statusCode"] == 504
    time.sleep(1.2)
    assert results and "already ended" in results[0]["error"]
    assert not any(c["tool"] == "submit_job" for c in tools.CALLS)
