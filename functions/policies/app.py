"""policies: GET /policies/{team} and PUT /policies/{team}  (Cognito JWT required)

Any signed-in user can read; only members of the `platform-leads` group can write.
"""

from backend import policies
from backend.http import error, handle, json_body, response


def claims(event: dict) -> dict:
    return ((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims", {})


def groups(c: dict) -> set[str]:
    raw = c.get("cognito:groups", "")
    if isinstance(raw, list):
        return set(raw)
    return {g for g in str(raw).strip("[]").replace(",", " ").split() if g}


@handle
def handler(event, context):
    team = (event.get("pathParameters") or {}).get("team", "")
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    c = claims(event)
    if not c:
        return error(401, "sign in required")
    if method == "PUT":
        if policies.LEAD_GROUP not in groups(c):
            return error(403, f"only {policies.LEAD_GROUP} can change team policies")
        return response(200, policies.put(team, json_body(event), c.get("email") or c.get("sub", "unknown")))
    policy = policies.get(team)
    return response(200, policy) if policy else error(404, f"no policy for team {team}")
