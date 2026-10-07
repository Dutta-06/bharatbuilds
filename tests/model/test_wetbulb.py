import pytest

from model.wetbulb import saturation_vapour_pressure_hpa, wet_bulb, wet_bulb_stull


@pytest.mark.parametrize("t,rh,expected", [
    (20, 50, 13.7),   # Stull (2011) worked example
    (30, 50, 22.0),   # standard psychrometric chart, sea level
    (25, 100, 25.0),  # saturated air: wet-bulb equals dry-bulb
])
def test_published_values(t, rh, expected):
    assert wet_bulb(t, rh) == pytest.approx(expected, abs=0.3)


def test_saturation_pressure_reference():
    # 6.112 hPa at 0 °C by definition; ~42.4 hPa at 30 °C (WMO tables)
    assert saturation_vapour_pressure_hpa(0) == pytest.approx(6.112)
    assert saturation_vapour_pressure_hpa(30) == pytest.approx(42.4, abs=0.3)


def test_agrees_with_stull_at_sea_level():
    # Stull (2011) reports its fit errs between -1 and +0.65 °C against the exact solution
    for t in (5, 15, 25, 35, 45):
        for rh in (15, 40, 70, 95):
            diff = wet_bulb_stull(t, rh) - wet_bulb(t, rh)
            assert -1.0 <= diff <= 1.0, (t, rh, diff)


def test_lower_pressure_lowers_wet_bulb():
    assert wet_bulb(30, 50, 850) < wet_bulb(30, 50, 1013.25)


def test_never_above_dry_bulb():
    for t in (0, 20, 40):
        for rh in (10, 50, 99):
            assert wet_bulb(t, rh) <= t + 1e-6


def test_rejects_bad_humidity():
    with pytest.raises(ValueError):
        wet_bulb(30, 0)
    with pytest.raises(ValueError):
        wet_bulb(30, 120)
