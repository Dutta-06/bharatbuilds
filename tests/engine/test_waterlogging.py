from engine.waterlogging import rolling_sums, thresholds_mm, waterlogging_levels


def test_rolling_sums_are_trailing_three_hours():
    assert rolling_sums([1, 2, 3, 4]) == [1, 3, 6, 9]


def test_dry_day_is_green():
    assert set(waterlogging_levels([0.0] * 48)) == {"green"}


def test_heavy_burst_is_red_everywhere():
    levels = waterlogging_levels([0, 15, 15, 15, 0])
    assert levels[3] == "red"


def test_hotspot_floods_earlier():
    rain = [0, 4, 4, 4, 0]  # 12 mm in 3 h
    assert set(waterlogging_levels(rain, has_hotspot=False)) == {"green"}
    assert "amber" in waterlogging_levels(rain, has_hotspot=True)


def test_low_lying_cell_has_lower_thresholds():
    assert thresholds_mm(False, 200, 216) == (15 * 0.75, 40 * 0.75)
    assert thresholds_mm(False, 214, 216) == (15, 40)
    assert thresholds_mm(True) == (7.5, 20)


def test_drainage_lag_keeps_amber_after_red():
    levels = waterlogging_levels([25, 25, 0, 0, 0, 0, 0], has_hotspot=True)
    # trailing sums: 25, 50, 50, 25, 0, 0, 0
    assert levels[:4] == ["red", "red", "red", "red"]
    assert levels[4:6] == ["amber", "amber"]
    assert levels[6] == "green"


def test_lead_in_rain_counts():
    assert waterlogging_levels([0], has_hotspot=True, lead_in=[10, 10]) == ["red"]
    assert waterlogging_levels([0], has_hotspot=True) == ["green"]
