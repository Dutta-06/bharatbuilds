import json
from datetime import datetime, timezone

import pytest

from backend import cities, db, risk_store

from .conftest import NOW, http_event, load_handler


@pytest.fixture
def get_risk(monkeypatch):
    # Pin "now" to the fixture's day: local_now is what the handler calls.
    monkeypatch.setattr(cities, "local_now", lambda tz, now_utc=None: NOW)
    return load_handler("get_risk")


@pytest.fixture
def seeded(aws, forecast):
    for cell in ("rohini", "zakhira"):
        rows, meta = risk_store.compute_rows("delhi", cell, forecast, now=NOW)
        risk_store.store(rows, meta)


def body(resp):
    return json.loads(resp["body"])


def test_get_risk_by_lat_lon(seeded, get_risk):
    resp = get_risk(http_event({"lat": "28.735", "lon": "77.112", "work": "heavy"}), None)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Cache-Control"] == "public, max-age=300"
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    b = body(resp)
    assert b["cell"]["id"] == "rohini"
    assert b["cell"]["distance_km"] < 1
    assert b["complete"] is True
    assert len(b["hazards"]["heat"]["strip"]) == 48
    assert b["hazards"]["heat"]["strip"][10]["level"] == "red"
    assert b["hazards"]["heat"]["sentences"]


def test_get_risk_by_cell_in_hindi(seeded, get_risk):
    b = body(get_risk(http_event({"city": "delhi", "cell": "zakhira", "lang": "hi"}), None))
    assert b["cell"]["name_hi"] == "ज़खीरा"
    assert "जलभराव" in " ".join(b["hazards"]["waterlogging"]["sentences"])


@pytest.mark.parametrize("query,status", [
    ({"lon": "77.1"}, 400),
    ({"lat": "abc", "lon": "77.1"}, 400),
    ({"lat": "28.7", "lon": "77.1", "work": "extreme"}, 400),
    ({"lat": "28.7", "lon": "77.1", "lang": "fr"}, 400),
    ({"lat": "19.07", "lon": "72.87"}, 404),  # Mumbai: no city file yet
    ({"city": "delhi", "cell": "atlantis"}, 404),
])
def test_get_risk_bad_requests(aws, get_risk, query, status):
    resp = get_risk(http_event(query), None)
    assert resp["statusCode"] == status
    assert "error" in body(resp)


def test_get_risk_no_data_is_503(aws, get_risk):
    resp = get_risk(http_event({"city": "delhi", "cell": "okhla"}), None)
    assert resp["statusCode"] == 503


def test_subscribe_stores_and_indexes(aws):
    subscribe = load_handler("subscribe")
    resp = subscribe(http_event(body={
        "device_id": "device-abc-123", "lat": 28.735, "lon": 77.112, "work": "heavy",
        "lang": "hi", "channel": "email", "contact": " Worker@Example.com",
    }), None)
    assert resp["statusCode"] == 201
    b = body(resp)
    assert b["cell"]["id"] == "rohini"
    assert b["contact"] == "w***@example.com"
    assert b["status"] == "pending_confirmation"

    item = db.get_item(db.user_pk("device-abc-123"), db.sub_sk("delhi", "rohini"))
    assert item["contact"] == "worker@example.com"
    assert item["hazards"] == ["heat", "waterlogging"]

    from boto3.dynamodb.conditions import Key
    hits = db.table().query(IndexName="GSI1",
                            KeyConditionExpression=Key("GSI1PK").eq("SUBS#delhi#rohini"))["Items"]
    assert [h["GSI1SK"] for h in hits] == ["USER#device-abc-123"]


def test_subscribe_generates_device_id(aws):
    resp = load_handler("subscribe")(http_event(body={
        "city": "delhi", "cell_id": "okhla", "contact": "a@b.in"}), None)
    assert resp["statusCode"] == 201
    assert len(body(resp)["device_id"]) == 32


@pytest.mark.parametrize("payload,status", [
    (None, 400),
    ({"city": "delhi", "cell_id": "okhla", "contact": "not-an-email"}, 400),
    ({"city": "delhi", "cell_id": "okhla", "contact": "a@b.in", "work": "x"}, 400),
    ({"city": "delhi", "cell_id": "okhla", "contact": "a@b.in", "hazards": ["fire"]}, 400),
    ({"city": "delhi", "cell_id": "okhla", "contact": "a@b.in", "channel": "sms"}, 400),
    ({"city": "delhi", "cell_id": "okhla", "contact": "a@b.in", "device_id": "x"}, 400),
    ({"city": "delhi", "cell_id": "nowhere", "contact": "a@b.in"}, 404),
    ({"lat": 19.07, "lon": 72.87, "contact": "a@b.in"}, 404),
])
def test_subscribe_rejects_bad_input(aws, payload, status):
    event = http_event(body=payload) if payload is not None else http_event()
    resp = load_handler("subscribe")(event, None)
    assert resp["statusCode"] == status


def test_subscribe_rejects_non_json_body(aws):
    resp = load_handler("subscribe")({"body": "{nope", "isBase64Encoded": False}, None)
    assert resp["statusCode"] == 400


def test_fetch_forecast_calls_open_meteo_for_the_cell(monkeypatch):
    from engine import openmeteo

    calls = []
    monkeypatch.setattr(openmeteo, "fetch_raw", lambda lat, lon: calls.append((lat, lon)) or {"ok": 1})
    out = load_handler("fetch_forecast")({"city": "delhi", "cell_id": "okhla"}, None)
    assert out == {"city": "delhi", "cell_id": "okhla", "forecast": {"ok": 1}}
    okhla = cities.city("delhi").cell("okhla")
    assert calls == [(okhla.lat, okhla.lon)]


def test_local_now_is_ist():
    utc = datetime(2026, 5, 26, 0, 0, tzinfo=timezone.utc)
    assert cities.local_now("Asia/Kolkata", utc) == datetime(2026, 5, 26, 5, 30)
