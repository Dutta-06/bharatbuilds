"""Helpers for API Gateway HTTP API (payload format 2.0) Lambda events."""

from __future__ import annotations

import base64
import json

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


class BadRequest(Exception):
    """Raised by handlers for client errors; becomes a 4xx response."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def response(status: int, body: dict, cache_seconds: int = 0) -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8", **CORS_HEADERS}
    headers["Cache-Control"] = f"public, max-age={cache_seconds}" if cache_seconds else "no-store"
    return {"statusCode": status, "headers": headers,
            "body": json.dumps(body, ensure_ascii=False)}


def error(status: int, message: str) -> dict:
    return response(status, {"error": message})


def query_params(event: dict) -> dict:
    return event.get("queryStringParameters") or {}


def json_body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if not raw:
        raise BadRequest("request body is required")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BadRequest(f"body is not valid JSON: {e.msg}") from e
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    return body


def handle(fn):
    """Decorator: turn BadRequest into a 4xx response and log anything else."""

    def wrapper(event, context):
        try:
            return fn(event, context)
        except BadRequest as e:
            return error(e.status, str(e))

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper
