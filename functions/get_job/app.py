"""get_job: GET /jobs (the queue, newest first) and GET /jobs/{id}."""

from backend import jobs
from backend.http import error, handle, query_params, response


@handle
def handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("id")
    if not job_id:
        try:
            limit = max(1, min(200, int(query_params(event).get("limit", 50))))
        except ValueError:
            limit = 50
        return response(200, {"jobs": jobs.queue(limit)})
    job = jobs.get(job_id)
    return response(200, job) if job else error(404, f"no job {job_id}")
