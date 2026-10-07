"""submit_job: POST /jobs

Body: {"gpu_hours": 4, "gpus": 1, "gpu": "a100", "deadline_h": 24 | "deadline": ISO UTC,
       "submit_region": "ap-south-1", "allowed_regions": [...], "data_residency": false,
       "max_delay_h": null, "weights": {"water": 0.5, "carbon": 0.5}, "name": "..."}
Places the job immediately and returns it (status "placed" or "infeasible").
Step 7 starts the run state machine from here.
"""

import json
import os
import time

import boto3

from backend import db, jobs, policies
from backend.http import handle, json_body, response


def start_run(job: dict) -> str | None:
    arn = os.environ.get("RUN_STATE_MACHINE_ARN")
    if not arn or job["status"] != "placed":
        return None
    sfn = boto3.client("stepfunctions", endpoint_url=db.endpoint_url())
    resp = sfn.start_execution(stateMachineArn=arn, name=f"job-{job['job_id']}",
                               input=json.dumps({"job_id": job["job_id"]}))
    return resp["executionArn"]


def emit_metrics(job: dict) -> None:
    """CloudWatch Embedded Metric Format: jobs placed, and modelled litres/kg saved."""
    saved = (job.get("preview_receipt") or {}).get("saved") or {}
    print(json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "Pravaah", "Dimensions": [[]],
            "Metrics": [{"Name": "JobsPlaced", "Unit": "Count"}, {"Name": "JobsInfeasible", "Unit": "Count"},
                        {"Name": "LitresSaved", "Unit": "None"}, {"Name": "KgCO2Saved", "Unit": "None"}]}]},
        "JobsPlaced": int(job["status"] == "placed"), "JobsInfeasible": int(job["status"] == "infeasible"),
        "LitresSaved": saved.get("litres", 0.0), "KgCO2Saved": saved.get("kg_co2", 0.0),
    }))


@handle
def handler(event, context):
    job = jobs.submit(policies.apply(json_body(event)))
    emit_metrics(job)
    execution = start_run(job)
    if execution:
        job["execution_arn"] = execution
    return response(201, job)
