from model.generator import fuel_rate


def test_interpolation_and_no_extrapolation():
    curve = {"source": "Test fixture only, not a real generator", "points": [
        {"load_fraction": .25, "litres_per_hour": 10}, {"load_fraction": .5, "litres_per_hour": 16},
        {"load_fraction": 1, "litres_per_hour": 30}]}
    assert fuel_rate(curve, 37.5, 100)["litres_per_hour"] == 13
    assert fuel_rate(curve, 10, 100)["status"] == "UNAVAILABLE"
    assert fuel_rate(curve, 110, 100)["status"] == "UNAVAILABLE"
    assert fuel_rate(None, 40, 100)["status"] == "UNAVAILABLE"


def test_curve_requires_sources_and_valid_points():
    assert fuel_rate({"points": []}, 40, 100)["status"] == "UNAVAILABLE"
    assert fuel_rate({"source": "fixture", "points": [{"load_fraction": .5, "litres_per_hour": 10}, {"load_fraction": .25, "litres_per_hour": 12}]}, 40, 100)["status"] == "UNAVAILABLE"
