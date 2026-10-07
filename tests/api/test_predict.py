import json

import pytest

from backend import db, forecasts
from forecasting import serve

from .conftest import NOW, load_handler


@pytest.fixture
def fake_models(tmp_path, monkeypatch):
    """A constant-output 'model' (one leaf) for t_wb and ci, marked use_model."""
    def const(value, features):
        return {"kind": "gbr", "features": features, "learning_rate": 1.0, "base": value,
                "trees": [], "verdict": {"use_model": True}}
    from forecasting.features import CARBON_FEATURES, WETBULB_FEATURES
    (tmp_path / "eu-north-1-t_wb.json").write_text(json.dumps(const(5.0, WETBULB_FEATURES)))
    (tmp_path / "eu-north-1-ci.json").write_text(json.dumps(const(42.0, CARBON_FEATURES)))
    (tmp_path / "us-east-1-t_wb.json").write_text(json.dumps({**const(1.0, WETBULB_FEATURES), "verdict": {"use_model": False}}))
    monkeypatch.setattr(serve, "MODELS", tmp_path)
    serve.load.cache_clear()
    yield
    serve.load.cache_clear()


def test_no_models_means_rows_pass_through(aws, frozen):
    rows = forecasts.collect("eu-north-1", offline=True)
    out = load_handler("predict")({"region": "eu-north-1", "rows": rows}, None)["rows"]
    assert out == rows


def test_models_apply_only_where_used(aws, frozen, fake_models):
    rows = forecasts.collect("eu-north-1", offline=True)
    rows[1]["ci_source"] = "electricitymaps-latest-held"
    out = load_handler("predict")({"region": "eu-north-1", "rows": rows}, None)["rows"]
    assert out[0]["t_wb"] == 5.0 and out[0]["t_wb_source"] == "model" and "t_wb_provider" in out[0]
    assert out[1]["ci_g_per_kwh"] == 42.0 and out[1]["ci_source"] == "model"
    assert out[0]["ci_source"] == "modelled"  # modelled profile rows are not "forecasts" to replace
    other = forecasts.collect("us-east-1", offline=True)
    assert load_handler("predict")({"region": "us-east-1", "rows": other}, None)["rows"] == other  # use_model false


def test_model_wetbulb_flows_into_cost(aws, frozen, fake_models):
    rows = serve.apply("eu-north-1", forecasts.collect("eu-north-1", offline=True))
    forecasts.store("eu-north-1", rows)
    conds = forecasts.to_conditions(forecasts.load(start=NOW, region_ids=["eu-north-1"])["eu-north-1"])
    assert conds[0].t_wb == 5.0


def test_forecast_error_scored_against_next_run(aws, frozen):
    rows = forecasts.collect("ap-south-1", offline=True)
    first = forecasts.store("ap-south-1", rows, run_id="r1")
    assert first["error"] is None                      # nothing to compare yet
    shifted = [dict(r, t_wb=r["t_wb"] + 1.0, ci_g_per_kwh=r["ci_g_per_kwh"] + 10) for r in rows]
    second = forecasts.store("ap-south-1", shifted, run_id="r2")
    err = second["error"]
    assert err["n"] == 3 and err["mae_t_wb"] == pytest.approx(1.0) and err["mae_ci"] == pytest.approx(10.0)
    assert db.get_item(db.forecast_pk("ap-south-1"), "ERROR#r2")["previous_run_id"] == "r1"


def test_surface_reports_forecast_error(seeded):
    rows = forecasts.collect("ap-south-1", start=NOW, offline=True)
    forecasts.store("ap-south-1", rows, run_id="again")
    from .conftest import body, http
    b = body(load_handler("get_surface")(http({"gpu_hours": "1"}), None))
    mumbai = next(r for r in b["regions"] if r["id"] == "ap-south-1")
    assert mumbai["forecast_error"]["n"] == 3 and mumbai["run_id"] == "again"
