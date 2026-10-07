import pytest

from model import coefficients
from model.water import calibration_factor, wue_grid, wue_site, wue_site_physics


def test_tower_is_zero_in_free_cooling_and_rises_with_wet_bulb():
    assert wue_site_physics(5, 10, "tower") == 0.0
    values = [wue_site_physics(wb, wb + 5, "tower") for wb in (8, 12, 15, 18, 25)]
    assert values == sorted(values)
    assert values[0] == 0.0 and values[-1] > 0


def test_tower_plateau_matches_physics():
    # full evaporation: 1.2 kWh heat × 3.6/2.43 kg/kWh × 5/4 cycles ≈ 2.22 L/kWh
    assert wue_site_physics(26, 30, "tower") == pytest.approx(1.2 * 3.6 / 2.43 * 1.25, rel=1e-6)


def test_tower_plateau_is_same_order_as_singapore_disclosure():
    # Singapore wet-bulb is ~25-27 °C all year; AWS discloses 1.68 L/kWh there.
    singapore = coefficients.load()["regional_wue"]["values"]["ap-southeast-1"]
    assert 0.6 < singapore / wue_site_physics(26, 30, "tower") < 1.4


def test_hybrid_runs_dry_longer_than_tower():
    assert wue_site_physics(15, 20, "hybrid") < wue_site_physics(15, 20, "tower")


def test_adiabatic_needs_air_above_setpoint():
    assert wue_site_physics(15, 20, "adiabatic") == 0.0
    hot = wue_site_physics(24, 35, "adiabatic")
    # 298 kg air/kWh × 1.006 × (35-27) / 2430 × 1.15 bleed ≈ 1.13 L/kWh
    assert hot == pytest.approx(3600 / (1.006 * 12) * 1.006 * 8 / 2430 * 1.15, rel=1e-6)


def test_adiabatic_cannot_cool_below_wet_bulb():
    # Humid: wet-bulb above setpoint means only cooling down to wet-bulb is possible
    assert wue_site_physics(29, 32, "adiabatic") < wue_site_physics(22, 32, "adiabatic")
    assert wue_site_physics(32, 32, "adiabatic") == 0.0


def test_air_cooled_uses_no_water():
    assert wue_site_physics(28, 40, "air") == 0.0


def test_unknown_cooling_type():
    with pytest.raises(ValueError):
        wue_site_physics(20, 25, "magic")


def test_calibration_hits_disclosed_mean():
    weather = [(wb, wb + 4) for wb in range(5, 28)]
    scale = calibration_factor(weather, "tower", 1.0)
    mean = sum(wue_site(wb, db, "tower", scale) for wb, db in weather) / len(weather)
    assert mean == pytest.approx(1.0)


def test_calibration_when_curve_is_zero_all_year():
    assert calibration_factor([(5, 10)] * 10, "adiabatic", 0.02) == 1.0


def test_grid_water_weighted_mean():
    assert wue_grid({"coal": 1.0}) == pytest.approx(2.60)
    assert wue_grid({"coal": 50, "wind": 50}) == pytest.approx(1.30)
    assert wue_grid({"wind": 0.5, "solar": 0.5}) < 0.01


def test_hydro_excluded_by_default_but_switchable():
    assert wue_grid({"hydro": 1.0}) == 0.0
    assert wue_grid({"hydro": 1.0}, include_hydro=True) == pytest.approx(17.0)


def test_unknown_source_treated_as_unknown():
    assert wue_grid({"tidal": 1.0}) == pytest.approx(0.75)


def test_empty_mix_rejected():
    with pytest.raises(ValueError):
        wue_grid({})
