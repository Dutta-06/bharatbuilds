"""Verify the real HTTP API lifecycle (SAM Local or an approved deployed API).

Uses only public GETs and authorized demo mutations; never deploys infrastructure.
"""
import argparse
import json
import os
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--token-env", default="TIDEWISE_ID_TOKEN")
    args = parser.parse_args()
    def call(path, payload=None):
        headers = {"Content-Type": "application/json"}
        token = os.environ.get(args.token_env)
        if token:
            headers["Authorization"] = token
        request = Request(args.url.rstrip("/") + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
            if "errorMessage" in result:
                raise RuntimeError(result["errorMessage"])
            if response.status == 202:
                import time
                for _ in range(30):
                    time.sleep(1)
                    view = call("/facilities/demo-delhi-01")
                    if view["facility"].get("last_event_id") == result["event_id"]:
                        return result
                raise RuntimeError("IoT publish remains pending; inspect logs")
            return result
    base = "/facilities/demo-delhi-01"
    def power(payload):
        return call(base + "/simulate-power", payload)
    power({"operation": "reset"})
    assert len(call(base)["workloads"]) == 6
    assert call(base)["facility"]["power_state"] == "GRID"
    power({"power_state": "BATTERY_TRANSITION"})
    import uuid
    event_id = uuid.uuid4().hex
    power({"power_state": "GENERATOR", "event_id": event_id})
    site = call(base)["facility"]
    assert site["metrics"]["baseline_it_kw"] == 55
    assert site["metrics"]["post_decision_it_kw"] == 27
    assert site["metrics"]["deferred_it_kw"] == 28
    version = site["version"]
    power({"power_state": "GENERATOR", "event_id": event_id})
    assert call(base)["facility"]["event_sequence"] == site["event_sequence"]
    power({"advance_s": 5400})
    assert call(base)["facility"]["metrics"]["deferred_it_kwh"] == 42
    power({"power_state": "GRID_RECOVERY"})
    assert call(base)["facility"]["power_state"] == "GRID_RECOVERY"
    power({"advance_s": 30})
    view = call(base)
    assert view["facility"]["power_state"] == "GRID"
    assert any(j["name"] == "ML Training" and j["status"] == "running" for j in view["workloads"])
    assert call(base + "/decisions")["decisions"]
    assert call("/facilities")["facilities"]
    assert call("/surface?gpu_hours=4")["regions"]
    original = call("/jobs", {"gpu_hours": 1, "deadline_h": 24, "name": "DG regression: normal cloud job"})
    assert "facility_id" not in original
    assert call("/jobs/" + original["job_id"])["job_id"] == original["job_id"]
    assert call("/jobs")["jobs"]
    print("PASS: persistent HTTP lifecycle, duplicate replay, 55 -> 27 kW, 28 kW, 42 kWh, recovery and existing Tidewise endpoints")


if __name__ == "__main__":
    main()
