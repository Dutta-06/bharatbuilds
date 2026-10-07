"""End-to-end on the synthetic Delhi fixture: parse -> assess -> CLI."""

import json
from datetime import datetime
from pathlib import Path

from engine import openmeteo
from engine.__main__ import main
from engine.risk import assess

FIXTURE = Path(__file__).parent / "fixtures" / "delhi_may_synthetic.json"


def forecast():
    return openmeteo.parse(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_parse_fixture():
    f = forecast()
    assert f.elevation == 214.0
    assert len(f.hours) == 78
    assert f.hours[0].wind is not None


def test_parse_skips_hours_missing_temperature_and_keeps_missing_solar_as_none():
    raw = {
        "hourly": {
            "time": ["2026-05-26T00:00", "2026-05-26T01:00"],
            "temperature_2m": [30.0, None],
            "relative_humidity_2m": [40, 40],
        }
    }
    f = openmeteo.parse(raw)
    assert len(f.hours) == 1
    assert f.hours[0].solar is None


def test_assess_48_hours_both_hazards():
    out = assess(forecast(), work="heavy", has_hotspot=True, city_ref_elevation_m=216,
                 now=datetime(2026, 5, 26, 5, 30))
    for hazard in ("heat", "waterlogging"):
        h = out["hazards"][hazard]
        assert len(h["strip"]) == 48
        assert h["strip"][0]["time"] == "2026-05-26T05:00"
        assert h["sentences"]
    heat = [s["level"] for s in out["hazards"]["heat"]["strip"]]
    # Afternoons are red for heavy work, and some hour in the 48 is not
    assert heat[10] == "red"  # 3 PM
    assert "green" in heat or "amber" in heat
    # The storm on the second evening floods the hotspot cell
    rain = [s["level"] for s in out["hazards"]["waterlogging"]["strip"]]
    assert "red" in rain[24:]
    assert set(rain[:24]) == {"green"}


def test_url_requests_what_the_engine_needs():
    url = openmeteo.forecast_url(28.7, 77.1)
    for var in openmeteo.HOURLY_VARS:
        assert var in url
    assert "wind_speed_unit=ms" in url


def test_cli_offline(capsys):
    code = main(["--from-file", str(FIXTURE), "--now", "2026-05-26T05:00", "--no-color",
                 "--lang", "hi", "--hotspot"])
    assert code == 0
    out = capsys.readouterr().out
    assert "भारी" in out
    assert "जलभराव" in out


def test_cli_city_cell_marks_hotspot(capsys):
    code = main(["--city", "delhi", "--cell", "zakhira", "--from-file", str(FIXTURE),
                 "--now", "2026-05-26T05:00", "--no-color", "--hazard", "waterlogging"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("Zakhira")
    assert "waterlogging hotspot" in out
