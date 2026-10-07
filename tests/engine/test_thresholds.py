import pytest

from engine.heat_index import heat_index
from engine.openmeteo import HourlyWeather
from engine.risk import assess_heat_hour
from engine.thresholds import heat_index_level, step_down, wbgt_level, worst
from engine.wbgt import wbgt_outdoor


def hour(t, rh, solar=None, wind=None):
    from datetime import datetime

    return HourlyWeather(datetime(2026, 5, 26, 13), t, rh, solar, wind, 0.0)


def test_delhi_44c_60rh_afternoon_is_red_for_heavy_work():
    assert assess_heat_hour(hour(44, 60, 850, 2), "heavy")["level"] == "red"
    # even without solar data (heat index fallback)
    assert assess_heat_hour(hour(44, 60), "heavy")["level"] == "red"


def test_28c_morning_is_green_for_heavy_work():
    r = assess_heat_hour(hour(28, 50, 150, 2), "heavy")
    assert r["metric"] == "wbgt"
    assert r["level"] == "green"


def test_heavy_is_stricter_than_light():
    w = wbgt_outdoor(36, 35, 600, 2)
    order = ["green", "amber", "red"]
    assert order.index(wbgt_level(w, "heavy")) >= order.index(wbgt_level(w, "light"))


@pytest.mark.parametrize(
    "wbgt,work,expected",
    [
        (25.9, "heavy", "amber"),
        (26.0, "heavy", "red"),
        (23.9, "heavy", "green"),
        (24.0, "heavy", "amber"),
        (27.9, "light", "green"),
        (28.0, "light", "amber"),
        (30.0, "light", "red"),
        (28.0, "moderate", "red"),
    ],
)
def test_iso_band_edges(wbgt, work, expected):
    assert wbgt_level(wbgt, work) == expected


def test_unacclimatised_is_stricter():
    assert wbgt_level(24, "heavy", acclimatised=True) == "amber"
    assert wbgt_level(24, "heavy", acclimatised=False) == "red"


def test_heat_index_bands():
    assert heat_index_level(26, "heavy") == "green"
    assert heat_index_level(30, "heavy") == "amber"
    assert heat_index_level(30, "light") == "green"
    assert heat_index_level(heat_index(40, 40), "light") == "red"


def test_falls_back_to_heat_index_without_solar():
    assert assess_heat_hour(hour(35, 40, None, 2), "heavy")["metric"] == "heat_index"
    assert assess_heat_hour(hour(35, 40, 500, None), "heavy")["metric"] == "heat_index"


def test_unknown_work_rejected():
    with pytest.raises(ValueError):
        wbgt_level(20, "extreme")


def test_level_helpers():
    assert worst("green", "red", "amber") == "red"
    assert step_down("red") == "amber"
    assert step_down("green") == "green"
