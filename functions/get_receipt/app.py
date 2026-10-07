"""get_receipt: GET /jobs/{id}/receipt

The final receipt (measured energy) once the job has run; until then 202 with
the modelled preview from placement time.
"""

from backend import jobs
from backend.http import error, handle, response


@handle
def handler(event, context):
    job_id = (event.get("pathParameters") or {}).get("id", "")
    final = jobs.get_receipt(job_id)
    if final:
        return response(200, final, cache_seconds=3600)
    job = jobs.get(job_id)
    if not job:
        return error(404, f"no job {job_id}")
    return response(202, {"job_id": job_id, "status": job["status"],
                          "final": False, "preview": job.get("preview_receipt")})
