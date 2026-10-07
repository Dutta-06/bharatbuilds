"""executor: the Lambda steps of the pravaah-run state machine.

Event: {"action": "load" | "launch" | "finish" | "fail", "job_id": ..., ...}
"""

from backend import executor


def handler(event, context):
    action = event["action"]
    job_id = event["job_id"]
    if action == "load":
        return executor.load(job_id)
    if action == "launch":
        return executor.launch(job_id, event["region"])
    if action == "finish":
        return executor.finish(job_id, event["run"])
    if action == "fail":
        return executor.fail(job_id, event.get("error"))
    raise ValueError(f"unknown action {action!r}")
