"""The shipped data files, the validator, and the grid helpers."""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_data import validate  # noqa: E402

from engine.grid import city_ids, haversine_km, hotspot_cells, load_city  # noqa: E402

DATA = ROOT / "data"


def test_shipped_data_has_no_errors():
    errors, _ = validate(DATA)
    assert errors == []


def test_delhi_grid_size_and_names():
    city = load_city("delhi")
    assert 50 <= len(city.cells) <= 70
    names = {c.name for c in city.cells}
    assert {"Rohini", "Dwarka", "Okhla"} <= names
    assert all(c.name_hi for c in city.cells)


def test_delhi_geography_is_the_right_way_round():
    city = load_city("delhi")
    c = {cell.id: cell for cell in city.cells}
    assert c["narela"].lat > c["rohini"].lat > c["connaught-place"].lat > c["saket"].lat
    assert c["najafgarh"].lon < c["dwarka"].lon < c["connaught-place"].lon < c["laxmi-nagar"].lon
    # trans-Yamuna localities are east of the old city
    for east in ("shahdara", "laxmi-nagar", "mayur-vihar", "preet-vihar"):
        assert c[east].lon > c["chandni-chowk"].lon


def test_nearest_cell():
    city = load_city("delhi")
    cell, km = city.nearest(28.7, 77.1)
    assert cell.id in {"rohini", "mangolpuri", "pitampura"}
    assert km < 4
    assert city.nearest(28.5246, 77.2066)[0].id == "saket"


def test_haversine_known_distance():
    # Connaught Place to India Gate is about 2.3 km
    assert haversine_km(28.6315, 77.2167, 28.6129, 77.2295) == pytest.approx(2.4, abs=0.2)


def test_hotspot_cells():
    assert {"connaught-place", "zakhira", "dhaula-kuan"} <= hotspot_cells("delhi")
    assert "narela" not in hotspot_cells("delhi")


@pytest.fixture
def data_copy(tmp_path):
    shutil.copytree(DATA, tmp_path / "data")
    return tmp_path / "data"


def edit(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_validator_catches_wrong_cell_id(data_copy):
    edit(data_copy / "hotspots" / "delhi.json",
         lambda d: d["hotspots"][0].update(cell_id="narela"))
    errors, _ = validate(data_copy)
    assert any("nearest cell is" in e for e in errors)


def test_validator_catches_point_outside_city(data_copy):
    edit(data_copy / "relief" / "delhi.json", lambda d: d["points"][0].update(lat=19.07, lon=72.87))
    errors, _ = validate(data_copy)
    assert any("outside the city bounds" in e for e in errors)


def test_validator_catches_schema_errors_and_duplicates(data_copy):
    def broken(d):
        d["cells"].append(dict(d["cells"][0]))
        d["cells"][1]["lat"] = "north-ish"

    edit(data_copy / "cities" / "delhi.json", broken)
    errors, _ = validate(data_copy)
    assert any("is not of type" in e for e in errors)


def test_validator_catches_cells_too_close(data_copy):
    def close(d):
        extra = dict(d["cells"][0], id="narela-2", lat=d["cells"][0]["lat"] + 0.001)
        d["cells"].append(extra)

    edit(data_copy / "cities" / "delhi.json", close)
    errors, _ = validate(data_copy)
    assert any("km apart" in e for e in errors)


def test_validator_catches_unknown_source(data_copy):
    edit(data_copy / "hotspots" / "delhi.json",
         lambda d: d["hotspots"][0].update(sources=["made-up"]))
    errors, _ = validate(data_copy)
    assert any("unknown source" in e for e in errors)


def test_adding_a_city_is_adding_a_file(data_copy):
    city = {
        "id": "testpur", "name": "Testpur", "name_hi": "टेस्टपुर", "timezone": "Asia/Kolkata",
        "bounds": {"south": 10, "west": 70, "north": 11, "east": 71}, "ref_elevation_m": 5,
        "cells": [
            {"id": "a", "name": "A", "name_hi": "ए", "lat": 10.2, "lon": 70.2, "elevation_m": 4},
            {"id": "b", "name": "B", "name_hi": "बी", "lat": 10.8, "lon": 70.8, "elevation_m": 6},
        ],
    }
    (data_copy / "cities" / "testpur.json").write_text(json.dumps(city), encoding="utf-8")
    errors, _ = validate(data_copy)
    assert errors == []
    assert "testpur" in city_ids(data_copy)
    assert load_city("testpur", data_copy).nearest(10.75, 70.7)[0].id == "b"
