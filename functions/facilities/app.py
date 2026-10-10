"""Public demo reads; Cognito platform-leads simulation mutations."""
import os
import json

from backend import facilities
from backend.http import BadRequest, handle, json_body, response


@handle
def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    fid = (event.get("pathParameters") or {}).get("id")
    if method == "GET":
        if not fid:
            return response(200, {"facilities": facilities.all_public()})
        if event.get("rawPath", "").endswith("/decisions"):
            return response(200, {"decisions": facilities.history(fid)})
        return response(200, facilities.view(fid))
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    # Explicit local mode is usable only in SAM Local, never from an HTTP header.
    local = os.environ.get("AWS_SAM_LOCAL") == "true" and os.environ.get("DG_LOCAL_SIMULATION") == "true"
    if not claims and not local:
        raise BadRequest("sign in required", 401)
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        try:
            parsed = json.loads(groups)
        except ValueError:
            parsed = None
        groups = parsed if isinstance(parsed, list) else groups.strip("[]").replace('"', '').replace("'", "").replace(",", " ").split()
    if not local and "platform-leads" not in groups:
        raise BadRequest("only platform-leads can operate simulated facilities", 403)
    body = json_body(event)
    if body.get("operation") == "reset":
        if fid != facilities.DEMO_ID:
            raise BadRequest("reset is restricted to the demonstration facility", 403)
        return response(200, facilities.reset_demo())
    telemetry = facilities.simulation_event(fid, body)
    if local:
        return response(200, facilities.process_event(telemetry))
    return response(202, facilities.publish(telemetry))
