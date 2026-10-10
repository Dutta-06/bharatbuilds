"""Resettable DG demo, trusted facility provisioning and IoT telemetry publisher.

Offline replay uses Moto's DynamoDB only, never a separate simulator policy.
Normal commands use configured AWS/LocalStack credentials and persistent table.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import db, facilities


def replay():
    import os
    from moto import mock_aws
    import boto3
    os.environ.update(AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test", AWS_DEFAULT_REGION="ap-south-1", TABLE_NAME="pravaah-dg-offline")
    os.environ.pop("AWS_ENDPOINT_URL", None)
    os.environ.pop("LOCAL_ENDPOINT_URL", None)
    with mock_aws():
        db.reset_clients()
        boto3.client("dynamodb").create_table(TableName=db.table_name(), BillingMode="PAY_PER_REQUEST", **db.TABLE_KEYS)
        facilities.reset_demo(datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc))
        for state, advance in [("BATTERY_TRANSITION", 1), ("GENERATOR", 1), ("GENERATOR", 5400), ("GRID_RECOVERY", 1), ("GRID_RECOVERY", 30)]:
            event = facilities.simulation_event(facilities.DEMO_ID, {"power_state": state, "advance_s": advance})
            facilities.process_event(event)
            assert facilities.process_event(event)["duplicate"]
            view = facilities.view(facilities.DEMO_ID)
            site = view["facility"]
            print(json.dumps({"power_state": site["power_state"], "time": site["simulation_time"], "metrics": site["metrics"],
                              "actions": [{"job_id": j["job_id"], "status": j["status"], "action": j["last_power_action"]} for j in view["workloads"]]}, indent=2))
            if state == "GENERATOR" and advance == 1:
                assert site["metrics"]["post_decision_it_kw"] == 27
            if advance == 5400:
                assert site["metrics"]["deferred_it_kwh"] == 42
        assert site["power_state"] == "GRID"
    db.reset_clients()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["offline-replay", "reset", "show", "event", "provision", "submit-cloud"])
    parser.add_argument("--facility", default=facilities.DEMO_ID)
    parser.add_argument("--state", choices=sorted(facilities.STATES))
    parser.add_argument("--advance-s", type=int, default=1)
    parser.add_argument("--event-id")
    parser.add_argument("--iot", action="store_true", help="Publish genuine AWS IoT Core telemetry instead of local processing")
    parser.add_argument("--file", type=Path, help="Facility configuration or trusted cloud-job JSON")
    args = parser.parse_args()
    if args.command == "offline-replay":
        replay()
        return
    if args.command == "reset":
        if args.facility != facilities.DEMO_ID:
            parser.error("reset is demo-only")
        result = facilities.reset_demo()
    elif args.command == "show":
        result = facilities.view(args.facility)
    elif args.command in {"provision", "submit-cloud"}:
        if not args.file:
            parser.error("--file is required")
        config = json.loads(args.file.read_text())
        if args.command == "provision":
            result = facilities.provision(config)
        else:
            from backend import jobs, policies
            import importlib.util
            result = jobs.submit(policies.apply(config))
            spec = importlib.util.spec_from_file_location("submit", Path(__file__).resolve().parents[1] / "functions/submit_job/app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result["execution_arn"] = module.start_run(result)
    else:
        payload = {"advance_s": args.advance_s}
        if args.state:
            payload["power_state"] = args.state
        if args.event_id:
            payload["event_id"] = args.event_id
        event = facilities.simulation_event(args.facility, payload)
        print(json.dumps({"telemetry": event}))
        result = facilities.publish(event) if args.iot else facilities.process_event(event)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
