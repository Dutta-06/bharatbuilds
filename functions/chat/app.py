"""chat: POST /chat {"message": "..."} -> {"reply", "tool_calls"}

Stateless: one question, one answer (multi-turn would keep Strands session state in DynamoDB).
The agent calls the public API through PRAVAAH_API_URL like any other client.
"""

import os

from assistant import agent, tools
from backend.http import BadRequest, handle, json_body, response


@handle
def handler(event, context):
    message = str(json_body(event).get("message", "")).strip()
    if not message or len(message) > 2000:
        raise BadRequest("message must be 1-2000 characters")
    # The agent calls this same API. Its URL comes from the request (a template reference
    # would be circular: the API references this function).
    domain = (event.get("requestContext") or {}).get("domainName")
    if domain and not os.environ.get("PRAVAAH_API_URL"):
        os.environ["PRAVAAH_API_URL"] = f"https://{domain}"
    tools.CALLS.clear()
    reply = agent.ask(message)
    return response(200, {"reply": reply, "tool_calls": list(tools.CALLS)})
