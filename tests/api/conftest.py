import importlib.util
import json
from datetime import datetime
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from backend import db

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "engine" / "fixtures" / "delhi_may_synthetic.json"
NOW = datetime(2026, 5, 26, 5, 0)  # local time inside the fixture


def load_handler(name: str):
    """Import functions/<name>/app.py under a unique module name."""
    spec = importlib.util.spec_from_file_location(f"fn_{name}", ROOT / "functions" / name / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("LOCAL_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("TABLE_NAME", "chhaanv-test")
    with mock_aws():
        db.reset_clients()
        boto3.client("dynamodb").create_table(
            TableName="chhaanv-test", BillingMode="PAY_PER_REQUEST", **db.TABLE_KEYS
        )
        yield
    db.reset_clients()


@pytest.fixture
def forecast():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def http_event(query=None, body=None):
    return {
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }
