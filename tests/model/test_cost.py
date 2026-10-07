import json
from dataclasses import replace

import pytest

from model import energy, regions
from model.__main__ import main
from model.cost import Conditions, Weights, cost, footprint, receipt

HOT_MUMBAI = Conditions("2026-10-10T09:00", t_db=33, rh=65, ci_g_per_kwh=680)
COOL_STOCKHOLM = Conditions("2026-10-10T02:00", t_db=8, rh=85, ci_g_per_kwh=35)


def test_job_energy():
    # 4 h × 0.4 kW × 0.7 utilisation × 1.3 overhead
    assert energy.job_it_kwh(4, "a100") == pytest.approx(4 * 0.4 * 0.7 * 1.3)
    with pytest.raises(ValueError):
        energy.job_it_kwh(4, "tpu")
    with pytest.raises(ValueError):
        energy.job_it_kwh(0)


def test_footprint_adds_up():
    r = regions.get("ap-south-1")
    fp = footprint(r, HOT_MUMBAI, 2.0)
    assert fp.facility_kwh == pytest.approx(2.0 * r.pue)
    assert fp.litres == pytest.approx(fp.litres_site + fp.litres_grid)
    assert fp.litres_site == pytest.approx(2.0 * fp.wue_site_l_per_kwh)
    assert fp.litres_grid == pytest.approx(fp.facility_kwh * fp.wue_grid_l_per_kwh)
    assert fp.kg_co2 == pytest.approx(fp.facility_kwh * 0.680)
    assert fp.litres_low < fp.litres < fp.litres_high
    assert fp.kg_low < fp.kg_co2 < fp.kg_high


def test_cool_clean_night_beats_hot_dirty_afternoon():
    mumbai, stockholm = regions.get("ap-south-1"), regions.get("eu-north-1")
    a = footprint(mumbai, HOT_MUMBAI, 2.0)
    b = footprint(stockholm, COOL_STOCKHOLM, 2.0)
    assert b.litres < a.litres and b.kg_co2 < a.kg_co2
    assert cost(b, stockholm, baseline=(a, mumbai)) < cost(a, mumbai, baseline=(a, mumbai)) == 1.0


def test_weights_change_the_ranking():
    # A slot that is wetter but cleaner should win only when carbon matters more.
    r = regions.get("ap-south-1")
    base = footprint(r, HOT_MUMBAI, 2.0)
    # A nuclear-heavy hour: low carbon but thirsty (2.54 L/kWh at the plant)
    wet_clean = footprint(r, replace(HOT_MUMBAI, ci_g_per_kwh=100, grid_mix={"nuclear": 1.0}), 2.0)
    assert wet_clean.litres > base.litres and wet_clean.kg_co2 < base.kg_co2
    water_first = Weights(water=1.0, carbon=0.0)
    carbon_first = Weights(water=0.0, carbon=1.0)
    assert cost(wet_clean, r, water_first, (base, r)) > 1.0
    assert cost(wet_clean, r, carbon_first, (base, r)) < 1.0


def test_water_stress_multiplies_water_term():
    r = regions.get("ap-south-1")
    stressed = replace(r, water_stress_score=5.0)
    fp = footprint(r, HOT_MUMBAI, 2.0)
    w = Weights(1.0, 0.0)
    assert cost(fp, stressed, w) == pytest.approx(2 * cost(fp, r, w))


def test_bad_weights():
    with pytest.raises(ValueError):
        Weights(0, 0)
    with pytest.raises(ValueError):
        Weights(-1, 1)


def test_receipt_estimated_and_measured():
    mumbai, stockholm = regions.get("ap-south-1"), regions.get("eu-north-1")
    base = footprint(mumbai, HOT_MUMBAI, 2.0)
    chosen = footprint(stockholm, COOL_STOCKHOLM, 2.0)
    r = receipt(chosen, base)
    assert r["energy_basis"] == "estimated"
    assert r["saved"]["litres"] == pytest.approx(base.litres - chosen.litres, abs=1e-3)
    assert 0 < r["saved"]["litres_pct"] <= 100

    measured = receipt(chosen, base, measured_it_kwh=1.0)
    assert measured["energy_basis"] == "measured"
    assert measured["chosen"]["it_kwh"] == 1.0
    # Halving the energy halves the savings; percentages are unchanged
    assert measured["saved"]["litres"] == pytest.approx(r["saved"]["litres"] / 2, rel=1e-3)
    assert measured["saved"]["litres_pct"] == r["saved"]["litres_pct"]
    # Measured energy narrows the band
    width = lambda d: d["litres_high"] - d["litres_low"]  # noqa: E731
    assert width(measured["chosen"]) < width(r["chosen"]) / 2
    json.dumps(measured)  # serialisable for the API


def test_missing_grid_mix():
    r = replace(regions.get("ap-south-1"), grid_mix={})
    with pytest.raises(ValueError):
        footprint(r, HOT_MUMBAI, 1.0)


def test_cli_offline(capsys):
    code = main(["--region", "ap-south-1", "--hour", "2026-10-10T09:00", "--gpu-hours", "4",
                 "--temp", "33", "--rh", "65", "--ci", "680"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ap-south-1" in out and "kg CO2" in out


def test_cli_compare_uses_live_weather(monkeypatch, capsys):
    from sources import openmeteo

    monkeypatch.setattr(openmeteo, "hour_weather", lambda lat, lon, hour: (30.0 if lat < 30 else 10.0, 70.0, 1010.0))
    code = main(["--region", "ap-south-1", "--hour", "2026-10-10T09:00Z", "--gpu-hours", "4",
                 "--compare", "--json"])
    assert code == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert len(rows) == len(regions.load())
    assert next(r for r in rows if r["region"] == "ap-south-1")["cost"] == 1.0
