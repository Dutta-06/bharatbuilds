"""reschedule_job: POST /jobs/{id}/reschedule

Moves a job that is waiting for its start to a better window, if the newest forecast has one
inside the job's own constraints. 200 {"rescheduled": true|false, ...}; 409 if the job is not waiting.
"""

from backend import replan
from backend.http import handle, response


@handle
def handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("id", "")
    return response(200, replan.reschedule(job_id))
