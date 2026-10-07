"""score_grid: place a job over the stored (region x hour) grid. Used by the run state machine.

Event:  {"job": <the request body accepted by POST /jobs>, "now"?: ISO UTC}
Return: the stored job record (with placement)
"""

from datetime import datetime

from backend import jobs


def handler(event, context):
    now = datetime.fromisoformat(event["now"].replace("Z", "")) if event.get("now") else None
    return jobs.submit(event["job"], now=now)
