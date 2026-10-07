import json
from datetime import datetime, timezone

import pytest

from model import regions
from sources import carbon, grid, openmeteo
from sources.carbon import CarbonSourceError, ElectricityMaps, ModelledProfile


def test_modelled_profile_dips_at_local_noon_and_keeps_daily_mean():
    p = ModelledProfile(500, {"coal": 0.7, "solar": 0.3}, lon=78.0)  # India, UTC+5.2 solar
    day = p.hours(datetime(2026, 10, 10, 0), 24)
    noon = p.at(datetime(2026, 10, 10, 7))     # ~12:12 local solar time
    night = p.at(datetime(2026, 10, 10, 19))   # ~00:12 local
    assert noon.ci_g_per_kwh < night.ci_g_per_kwh
    assert sum(g.ci_g_per_kwh for g in day) / 24 == pytest.approx(500, rel=0.05)
    assert all(g.source == "modelled" for g in day)


def test_no_solar_means_flat_profile():
    p = ModelledProfile(480, {"gas": 1.0}, lon=103.8)
    assert {g.ci_g_per_kwh for g in p.hours(datetime(2026, 10, 10), 24)} == {480.0}


def test_for_region_without_token_uses_profile(monkeypatch):
    monkeypatch.delenv("ELECTRICITYMAPS_TOKEN", raising=False)
    assert isinstance(carbon.for_region(regions.get("ap-south-1")), ModelledProfile)
    with pytest.raises(CarbonSourceError):
        ElectricityMaps()


def test_electricitymaps_parsing(monkeypatch):
    monkeypatch.setenv("ELECTRICITYMAPS_TOKEN", "t")
    responses = {
        "carbon-intensity/history": {"history": [
            {"datetime": "2026-10-10T05:00:00.000Z", "carbonIntensity": 610},
            {"datetime": "2026-10-10T06:00:00.000Z", "carbonIntensity": None},
        ]},
        "power-breakdown/history": {"history": [
            {"datetime": "2026-10-10T05:00:00.000Z",
             "powerConsumptionBreakdown": {"coal": 700, "hydro discharge": 50, "solar": 0, "battery discharge": 5}},
        ]},
    }
    em = ElectricityMaps()
    monkeypatch.setattr(em, "_get", lambda path, **kw: responses[path])
    h = em.history("IN-WE")
    assert len(h) == 1
    assert h[0].hour == "2026-10-10T05:00" and h[0].ci_g_per_kwh == 610
    assert h[0].mix == {"coal": 700, "hydro": 50}


def test_outlook_falls_back_to_latest_held_when_forecast_unavailable(monkeypatch):
    monkeypatch.setenv("ELECTRICITYMAPS_TOKEN", "t")
    em = ElectricityMaps()
    monkeypatch.setattr(carbon, "for_region", lambda r: em)
    monkeypatch.setattr(em, "latest", lambda zone: carbon.GridHour("2026-10-10T05:00", 600, {"coal": 1}, "electricitymaps"))

    def no_forecast(zone):
        raise CarbonSourceError("HTTP 403")

    monkeypatch.setattr(em, "forecast", no_forecast)
    monkeypatch.setattr(grid, "for_region", carbon.for_region)
    out = grid.outlook(regions.get("ap-south-1"), datetime(2026, 10, 10, 5), hours=3)
    assert [g.source for g in out] == ["electricitymaps-latest-held"] * 3
    assert out[0].mix == {"coal": 1}


def test_outlook_without_token_is_modelled(monkeypatch):
    monkeypatch.delenv("ELECTRICITYMAPS_TOKEN", raising=False)
    out = grid.outlook(regions.get("eu-north-1"), datetime(2026, 10, 10, 0), hours=48)
    assert len(out) == 48 and out[0].hour == "2026-10-10T00:00"
    assert {g.source for g in out} == {"modelled"}


def test_openmeteo_recent_rejects_long_ranges():
    with pytest.raises(ValueError):
        openmeteo.recent(0, 0, 120)


def test_openmeteo_forecast_filters_past_and_nulls(monkeypatch):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    times = ["2000-01-01T00:00", now, "2999-01-01T00:00", "2999-01-01T01:00"]
    monkeypatch.setattr(openmeteo, "_get", lambda url, params, timeout=15.0: {"hourly": {
        "time": times, "temperature_2m": [1, 2, 3, None], "relative_humidity_2m": [50] * 4,
        "surface_pressure": [1000] * 4}})
    rows = openmeteo.forecast(0, 0, hours=48)
    assert [r[0] for r in rows] == [now, "2999-01-01T00:00"]
    json.dumps(rows)
