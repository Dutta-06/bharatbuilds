"""DynamoDB single-table access. Key shapes and access patterns: docs/data-model.md."""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Key

DEFAULT_TABLE = "pravaah-main"

# Shared by scripts/local_setup.py and the tests; template.yaml mirrors it
# (tests/api/test_template.py checks they agree).
TABLE_KEYS = {
    "AttributeDefinitions": [
        {"AttributeName": n, "AttributeType": "S"} for n in ("PK", "SK", "GSI1PK", "GSI1SK")
    ],
    "KeySchema": [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"},
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": "GSI1",
            "KeySchema": [
                {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }
    ],
}


def table_name() -> str:
    return os.environ.get("TABLE_NAME", DEFAULT_TABLE)


def endpoint_url() -> str | None:
    """LocalStack endpoint when running locally, None (real AWS) otherwise.

    sam local only passes variables declared in template.yaml, so it uses
    LOCAL_ENDPOINT_URL; scripts on the host can use AWS_ENDPOINT_URL.
    """
    return os.environ.get("LOCAL_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL") or None


@lru_cache(maxsize=1)
def _resource():
    return boto3.resource("dynamodb", endpoint_url=endpoint_url())


def table():
    return _resource().Table(table_name())


def reset_clients() -> None:
    """Forget cached clients (tests switch endpoints)."""
    _resource.cache_clear()


# --- keys -------------------------------------------------------------------

def forecast_pk(region: str) -> str:
    return f"FORECAST#{region}"


def hour_sk(utc_hour: str) -> str:
    return f"HOUR#{utc_hour}"


META_LATEST = "META#latest"
META = "META"


def job_pk(job_id: str) -> str:
    return f"JOB#{job_id}"


def receipt_pk(job_id: str) -> str:
    return f"RECEIPT#{job_id}"


def policy_pk(team: str) -> str:
    return f"POLICY#{team}"


JOBS_INDEX_PK = "JOBS"  # GSI1: every job, sorted by submit time (the queue)


# --- conversion -------------------------------------------------------------

def to_dynamo(value):
    """Floats -> Decimal, recursively (DynamoDB rejects float)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dynamo(v) for v in value]
    return value


def from_dynamo(value):
    """Decimal -> int or float, recursively, for JSON responses."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_dynamo(v) for v in value]
    return value


# --- operations -------------------------------------------------------------

def put_items(items: list[dict]) -> int:
    with table().batch_writer() as batch:
        for item in items:
            batch.put_item(Item=to_dynamo(item))
    return len(items)


def put_item(item: dict) -> None:
    table().put_item(Item=to_dynamo(item))


def get_item(pk: str, sk: str) -> dict | None:
    item = table().get_item(Key={"PK": pk, "SK": sk}).get("Item")
    return from_dynamo(item) if item else None


def query(key_condition, index: str | None = None, forward: bool = True, limit: int | None = None) -> list[dict]:
    kwargs = {"KeyConditionExpression": key_condition, "ScanIndexForward": forward}
    if index:
        kwargs["IndexName"] = index
    items: list[dict] = []
    while True:
        if limit:
            kwargs["Limit"] = limit - len(items)
        resp = table().query(**kwargs)
        items += resp["Items"]
        if "LastEvaluatedKey" not in resp or (limit and len(items) >= limit):
            return [from_dynamo(i) for i in items]
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def forecast_hours(region: str, first: str, last: str) -> list[dict]:
    return query(Key("PK").eq(forecast_pk(region)) & Key("SK").between(hour_sk(first), hour_sk(last)))


def recent_jobs(limit: int = 50) -> list[dict]:
    return query(Key("GSI1PK").eq(JOBS_INDEX_PK), index="GSI1", forward=False, limit=limit)
