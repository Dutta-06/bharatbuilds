import pytest

from engine.heat_index import heat_index
from engine.wbgt import globe_temperature, wbgt_bom, wbgt_outdoor, wet_bulb_stull


def test_stull_reference_value():
    # Stull (2011) paper example: 20 °C, 50 % RH -> 13.7 °C
    assert wet_bulb_stull(20, 50) == pytest.approx(13.7, abs=0.1)


def test_wet_bulb_never_exceeds_air_temperature():
    for t in (10, 25, 35, 45):
        for rh in (10, 40, 70, 95):
            assert wet_bulb_stull(t, rh) <= t + 0.5


def test_bom_known_value():
    # 30 °C, 50 % RH: e = 21.1 hPa -> WBGT = 0.567*30 + 0.393*21.1 + 3.94
    assert wbgt_bom(30, 50) == pytest.approx(29.3, abs=0.1)


def test_globe_equals_air_at_night():
    assert globe_temperature(32, 0, 2) == 32


def test_globe_hotter_in_sun_and_cooler_with_wind():
    calm = globe_temperature(35, 900, 0.5)
    windy = globe_temperature(35, 900, 8)
    assert calm > windy > 35
    # light-wind full sun: 10-25 °C above air is the observed range
    assert 10 < calm - 35 < 25


def test_outdoor_agrees_with_bom_at_bom_reference_conditions():
    # BoM assumes moderately high radiation and light wind; at moderate
    # humidity the two estimates should be close.
    assert wbgt_outdoor(30, 50, 700, 2) == pytest.approx(wbgt_bom(30, 50), abs=2.5)


def test_outdoor_increases_with_sun_and_humidity():
    assert wbgt_outdoor(35, 40, 800, 2) > wbgt_outdoor(35, 40, 0, 2)
    assert wbgt_outdoor(35, 70, 0, 2) > wbgt_outdoor(35, 30, 0, 2)


def test_heat_index_noaa_table():
    # NWS table: 96 °F at 65 % RH -> 121 °F (49.4 °C)
    assert heat_index(35.56, 65) == pytest.approx(49.4, abs=1.0)
    # below 80 °F the simple formula is used and stays near air temperature
    assert heat_index(22, 50) == pytest.approx(22, abs=1.5)
