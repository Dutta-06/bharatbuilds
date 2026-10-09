"""chat: POST /chat {"message": "..."} -> {"reply", "tool_calls"}

Stateless: one question, one answer (multi-turn would keep Strands session state in DynamoDB).
The agent calls the public API through PRAVAAH_API_URL like any other client.

API Gateway cuts a request off at 30 s with a bare "Service Unavailable". The free language models can be
slower than that, so the handler gives the model a budget a little under it and answers with a clear message
instead (CHAT_BUDGET_S, default 24). A provider failure (rate limit, model withdrawn) gets the same treatment.
"""

import concurrent.futures as cf
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
    request = tools.begin_request()

    def work():
        tools.bind(request)
        return agent.ask(message)

    pool = cf.ThreadPoolExecutor(max_workers=1)
    try:
        reply = pool.submit(work).result(timeout=float(os.environ.get("CHAT_BUDGET_S", "24")))
    except cf.TimeoutError:
        tools.expire()                          # the slow model thread can no longer submit or read anything
        submitted = any(c["tool"] == "submit_job" for c in tools.CALLS)
        return response(504, {"error": "The assistant took too long to answer. "
                              + ("It may already have submitted your job, so check the Queue before asking again."
                                 if submitted else "Try again, or place the job on the Submit page.")})
    except Exception as e:                      # provider down, rate-limited, or the model was withdrawn
        print(f"chat model error: {type(e).__name__}: {e}"[:500])
        return response(503, {"error": "The assistant's language model is unavailable right now, possibly rate-limited. "
                                       "You can still place a job on the Submit page."})
    finally:
        pool.shutdown(wait=False)
    return response(200, {"reply": reply, "tool_calls": list(tools.CALLS)})
