from datetime import timedelta

import pytest

from backend import db, forecasts, jobs

from .conftest import NOW, body, http, load_handler


def test_collect_offline_is_labelled(aws):
    rows = forecasts.collect("eu-north-1", start=NOW, offline=True)
    assert len(rows) == 48 and rows[0]["hour"] == "2026-10-10T06:00"
    assert {r["weather_source"] for r in rows} == {"synthetic"}
    assert {r["ci_source"] for r in rows} == {"modelled"}
    assert all(r["t_wb"] <= r["t_db"] for r in rows)


def test_store_and_load_round_trip(seeded):
    meta = db.get_item(db.forecast_pk("eu-north-1"), db.META_LATEST)
    assert meta["hours"] == 48 and meta["weather_sources"] == ["synthetic"]
    stored = forecasts.load(start=NOW)
    assert len(stored["ap-south-1"]) == 48
    assert stored["eu-west-1"] == []  # not seeded
    assert isinstance(stored["ap-south-1"][0]["t_db"], float)


def test_fetch_then_store_handlers(aws, frozen):
    out = load_handler("fetch_forecast")({"region": "us-east-1", "offline": True}, None)
    assert len(out["rows"]) == 48 and out["raw_key"] is None
    meta = load_handler("store_forecast")({**out, "run_id": "r1"}, None)
    assert meta["run_id"] == "r1" and meta["hours"] == 48


def test_get_surface(seeded):
    resp = load_handler("get_surface")(http({"gpu_hours": "4"}), None)
    assert resp["statusCode"] == 200
    b = body(resp)
    assert len(b["hours"]) == 48
    assert {r["id"] for r in b["regions"]} == {"ap-south-1", "ap-southeast-1", "eu-north-1", "us-east-1"}
    mumbai = next(r for r in b["regions"] if r["id"] == "ap-south-1")
    assert mumbai["cells"][0]["cost"] == pytest.approx(1.0)
    assert b["best"]["cost"] < 1.0
    assert mumbai["ci_sources"] == ["modelled"] and mumbai["weather_sources"] == ["synthetic"]
    cell = mumbai["cells"][0]
    assert cell["litres_low"] <= cell["litres"] <= cell["litres_high"]


def test_get_surface_errors(aws, frozen):
    h = load_handler("get_surface")
    assert h(http({"gpu_hours": "abc"}), None)["statusCode"] == 400
    assert h(http({"gpu": "tpu"}), None)["statusCode"] == 400
    assert h(http({"baseline": "mars-1"}), None)["statusCode"] == 400
    assert h(http({}), None)["statusCode"] == 503  # nothing stored


def test_regions_route(aws):
    b = body(load_handler("get_surface")(http(path="/regions"), None))
    assert len(b["regions"]) == 8 and {"id", "lat", "lon", "geo"} <= set(b["regions"][0])


def test_submit_job_places_and_stores(seeded):
    resp = load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 24,
                                                 "submit_region": "ap-south-1", "name": "demo"}), None)
    assert resp["statusCode"] == 201
    job = body(resp)
    assert job["status"] == "placed"
    p = job["placement"]
    assert p["chosen"]["region"] != "ap-south-1" or p["chosen"]["start"] != p["baseline"]["start"]
    assert p["chosen"]["cost"] < 1.0
    assert job["preview_receipt"]["saved"]["litres"] > 0
    assert "execution_arn" not in job  # no state machine configured

    got = body(load_handler("get_job")(http(path_params={"id": job["job_id"]}), None))
    assert got["job_id"] == job["job_id"] and got["name"] == "demo"
    queue = body(load_handler("get_job")(http(), None))["jobs"]
    assert [j["job_id"] for j in queue] == [job["job_id"]]


def test_submit_infeasible_is_stored_with_reason(seeded):
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 10, "deadline_h": 2}), None))
    assert job["status"] == "infeasible"
    assert "cannot finish" in job["placement"]["reason"]


@pytest.mark.parametrize("payload", [
    {"deadline_h": 5},                                    # no gpu_hours
    {"gpu_hours": 4},                                     # no deadline
    {"gpu_hours": 4, "deadline_h": 5, "gpu": "tpu"},
    {"gpu_hours": 4, "deadline_h": 5, "submit_region": "mars-1"},
    {"gpu_hours": 4, "deadline_h": 5, "allowed_regions": ["mars-1"]},
    {"gpu_hours": 4, "deadline": "tomorrow"},
    {"gpu_hours": 4, "deadline_h": 5, "weights": {"water": -1}},
    {"gpu_hours": -1, "deadline_h": 5},
])
def test_submit_rejects_bad_input(seeded, payload):
    assert load_handler("submit_job")(http(body=payload), None)["statusCode"] == 400


def test_receipt_preview_then_final(seeded):
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 2, "deadline_h": 12}), None))
    h = load_handler("get_receipt")
    pending = h(http(path_params={"id": job["job_id"]}), None)
    assert pending["statusCode"] == 202 and body(pending)["final"] is False
    db.put_item({"PK": db.receipt_pk(job["job_id"]), "SK": db.META, "job_id": job["job_id"],
                 "final": True, "energy_basis": "measured"})
    final = h(http(path_params={"id": job["job_id"]}), None)
    assert final["statusCode"] == 200 and body(final)["energy_basis"] == "measured"
    assert h(http(path_params={"id": "nope"}), None)["statusCode"] == 404


def test_score_grid_handler(seeded):
    out = load_handler("score_grid")({"job": {"gpu_hours": 1, "deadline_h": 6}, "now": "2026-10-10T06:10Z"}, None)
    assert out["status"] == "placed"


def test_deadline_iso_parsing():
    now = NOW
    j = jobs.parse({"gpu_hours": 1, "deadline": "2026-10-10T20:00+05:30"}, now)
    assert j.deadline == NOW + timedelta(hours=8, minutes=30)


def test_submit_emits_emf_metrics(seeded, capsys):
    import json as _json
    load_handler("submit_job")(http(body={"gpu_hours": 2, "deadline_h": 12}), None)
    line = _json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["JobsPlaced"] == 1 and line["LitresSaved"] > 0
    assert line["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "Pravaah"


def test_submit_splittable_job_includes_plan(seeded):
    job = body(load_handler("submit_job")(http(body={"gpu_hours": 20, "deadline_h": 40, "splittable": True,
                                                     "max_chunks": 2}), None))
    plan = job["split_plan"]
    assert plan["feasible"] and len(plan["chunks"]) <= 2
    assert sum(c["hours"] for c in plan["chunks"]) == 20
    assert "design-only" in plan["note"]
