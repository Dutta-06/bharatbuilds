"""DynamoDB single-table access. Key shapes are documented in docs/data-model.md."""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

import boto3

DEFAULT_TABLE = "chhaanv-main"

# Shared by scripts/local_setup.py and the tests; template.yaml mirrors it
# (tests/backend/test_template.py checks they agree).
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
    LOCAL_ENDPOINT_URL; scripts run on the host can use AWS_ENDPOINT_URL.
    """
    return os.environ.get("LOCAL_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL") or None


@lru_cache(maxsize=1)
def _resource():
    return boto3.resource("dynamodb", endpoint_url=endpoint_url())


def table():
    return _resource().Table(table_name())


def reset_clients() -> None:
    """Forget cached clients (tests switch endpoints and regions)."""
    _resource.cache_clear()


# --- keys -------------------------------------------------------------------

def cell_pk(city: str, cell_id: str) -> str:
    return f"CELL#{city}#{cell_id}"


def hour_sk(local_iso: str) -> str:
    return f"HOUR#{local_iso}"


META_LATEST = "META#latest"


def user_pk(user_id: str) -> str:
    return f"USER#{user_id}"


def sub_sk(city: str, cell_id: str) -> str:
    return f"SUB#{city}#{cell_id}"


def subs_gsi_pk(city: str, cell_id: str) -> str:
    return f"SUBS#{city}#{cell_id}"


# --- conversion -------------------------------------------------------------

def to_dynamo(value):
    """Floats -> Decimal, recursively (DynamoDB rejects float)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
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


def query_hours(city: str, cell_id: str, first_iso: str, last_iso: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    kwargs = {
        "KeyConditionExpression": Key("PK").eq(cell_pk(city, cell_id))
        & Key("SK").between(hour_sk(first_iso), hour_sk(last_iso)),
    }
    items: list[dict] = []
    while True:
        resp = table().query(**kwargs)
        items += resp["Items"]
        if "LastEvaluatedKey" not in resp:
            return [from_dynamo(i) for i in items]
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def get_item(pk: str, sk: str) -> dict | None:
    item = table().get_item(Key={"PK": pk, "SK": sk}).get("Item")
    return from_dynamo(item) if item else None
