import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from backend import db, forecasts

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 10, 6, 0)  # UTC


def load_handler(name: str):
    spec = importlib.util.spec_from_file_location(f"fn_{name}", ROOT / "functions" / name / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


@pytest.fixture
def aws(monkeypatch):
    for k, v in {"AWS_DEFAULT_REGION": "ap-south-1", "AWS_ACCESS_KEY_ID": "test",
                 "AWS_SECRET_ACCESS_KEY": "test", "TABLE_NAME": "pravaah-test"}.items():
        monkeypatch.setenv(k, v)
    for k in ("AWS_ENDPOINT_URL", "LOCAL_ENDPOINT_URL", "BUCKET_NAME", "RUN_STATE_MACHINE_ARN",
              "ELECTRICITYMAPS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with mock_aws():
        db.reset_clients()
        boto3.client("dynamodb").create_table(TableName="pravaah-test", BillingMode="PAY_PER_REQUEST",
                                              **db.TABLE_KEYS)
        yield
    db.reset_clients()


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(forecasts, "utc_now", lambda: NOW + timedelta(minutes=12))


@pytest.fixture
def seeded(aws, frozen):
    for rid in ("ap-south-1", "ap-southeast-1", "eu-north-1", "us-east-1"):
        forecasts.store(rid, forecasts.collect(rid, start=NOW, offline=True), run_id="test-run")


def http(query=None, body=None, path="/", path_params=None):
    return {"rawPath": path, "queryStringParameters": query, "pathParameters": path_params,
            "body": json.dumps(body) if body is not None else None, "isBase64Encoded": False}


def body(resp):
    return json.loads(resp["body"])
