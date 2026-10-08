"""Grade the assistant against evals/assistant.yaml (plan: at least 16 of 20).

    pip install -r requirements-assistant.txt
    ANTHROPIC_API_KEY=... python -m assistant.eval          # or ASSISTANT_PROVIDER=bedrock | openai
    ASSISTANT_PROVIDER=openai LLM_BASE_URL=... LLM_MODEL_ID=... LLM_API_KEY=... python -m assistant.eval

Runs against a stub API on localhost (canned surface/job/receipt responses), so it costs
model tokens only, about 20 short agent turns, and never touches real data. Each case is
graded on the tool calls the agent made, not on the wording of its reply.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from . import tools

CASES = Path(__file__).resolve().parent.parent / "evals" / "assistant.yaml"
REGION_GEO = {"ap-south-1": "IN", "ap-south-2": "IN", "ap-southeast-1": "SG", "eu-north-1": "EU",
              "eu-west-1": "EU", "eu-central-1": "EU", "us-east-1": "US", "us-west-2": "US"}


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def grade(expect: dict, calls: list[dict], now: datetime) -> tuple[bool, list[str]]:
    problems: list[str] = []
    want = expect["tool"]
    submits = [c for c in calls if c["tool"] == "submit_job"]
    if want == "none":
        if calls:
            problems.append(f"expected a clarifying question, got tool calls {[c['tool'] for c in calls]}")
        return not problems, problems
    if expect.get("no_submit") and submits:
        problems.append("submitted a job for a question that only asked where/when")
    matching = [c for c in calls if c["tool"] == want]
    if not matching:
        return False, [f"never called {want}"]
    call = matching[-1]["args"]
    if want == "get_receipt":
        if call.get("job_id") != expect["job_id"]:
            problems.append(f"job_id {call.get('job_id')!r} != {expect['job_id']!r}")
        return not problems, problems
    if want != "submit_job":
        return not problems, problems

    def eq(key, got, tol=1e-6):
        if key in expect and abs(float(got) - float(expect[key])) > tol:
            problems.append(f"{key} {got} != {expect[key]}")

    eq("gpu_hours", call.get("gpu_hours", 0))
    eq("gpus", call.get("gpus", 1))
    eq("water", call["weights"]["water"], 0.05)
    eq("carbon", call["weights"]["carbon"], 0.05)
    if "gpu" in expect and call.get("gpu", "a100").lower() != expect["gpu"]:
        problems.append(f"gpu {call.get('gpu')} != {expect['gpu']}")
    if "submit_region" in expect and call.get("submit_region") != expect["submit_region"]:
        problems.append(f"submit_region {call.get('submit_region')} != {expect['submit_region']}")
    for flag, geo in (("india_only", "IN"), ("eu_only", "EU"), ("us_only", "US")):
        if expect.get(flag):
            allowed = call.get("allowed_regions")
            ok = (allowed and all(REGION_GEO.get(r) == geo for r in allowed)) or \
                 (call.get("data_residency") and REGION_GEO.get(call.get("submit_region")) == geo)
            if not ok:
                problems.append(f"not restricted to {geo}")
    if "deadline_between" in expect:
        lo, hi = (_ts(x) for x in expect["deadline_between"])
        if call.get("deadline"):
            deadline = _ts(call["deadline"])
        elif call.get("deadline_h") is not None:
            from datetime import timedelta
            deadline = now + timedelta(hours=float(call["deadline_h"]))
        else:
            deadline = None
        if deadline is None or not lo <= deadline <= hi:
            problems.append(f"deadline {deadline} not in [{lo}, {hi}]")
    return not problems, problems


class _Stub(BaseHTTPRequestHandler):
    def _send(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/surface"):
            cells = lambda base: [{"hour": f"2026-10-07T{h:02d}:00", "cost": base + 0.01 * h,  # noqa: E731
                                   "litres": 2 * base, "kg_co2": base} for h in range(12, 24)]
            self._send({"best": {"region": "eu-north-1", "hour": "2026-10-07T20:00", "cost": 0.12},
                        "baseline": {"region": "ap-south-1", "hour": "2026-10-07T12:00"}, "window_end": "2026-10-09T11:00",
                        "regions": [{"id": rid, "cells": cells(c), "weather_sources": ["stub"], "ci_sources": ["stub"]}
                                    for rid, c in (("ap-south-1", 1.0), ("eu-north-1", 0.12), ("us-west-2", 0.2))]})
        elif "/receipt" in self.path:
            self._send({"final": False, "preview": {"saved": {"litres": 5.1, "litres_pct": 80, "kg_co2": 0.9, "kg_co2_pct": 70}}}, 202)
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        self._send({"job_id": "stub01", "status": "placed",
                    "placement": {"reason": f"Run in eu-north-1 tonight; {body.get('gpu_hours')} GPU-hours.",
                                  "chosen": {"region": "eu-north-1", "start": "2026-10-07T20:00"}},
                    "preview_receipt": {"saved": {"litres": 5.0, "litres_pct": 80}}}, 201)


def run(agent_factory=None) -> int:
    import os

    from .agent import ask, build_agent

    spec = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    now = _ts(spec["now"])
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["PRAVAAH_API_URL"] = f"http://127.0.0.1:{server.server_address[1]}"
    passed = 0
    for i, case in enumerate(spec["cases"], 1):
        tools.CALLS.clear()
        agent = (agent_factory or build_agent)()
        reply = ask(case["q"], agent=agent, now=now)
        ok, problems = grade(case["expect"], list(tools.CALLS), now)
        passed += ok
        print(f"{i:2} {'PASS' if ok else 'FAIL'}  {case['q'][:60]}")
        if not ok:
            print(f"     {'; '.join(problems)}\n     reply: {reply[:160]}")
    server.shutdown()
    print(f"\n{passed}/{len(spec['cases'])} passed (pass mark {spec['pass_mark']})")
    return 0 if passed >= spec["pass_mark"] else 1


if __name__ == "__main__":
    sys.exit(run())
