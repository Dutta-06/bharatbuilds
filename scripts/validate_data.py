"""Validate every file under data/ against its JSON schema, plus cross-file checks.

    python scripts/validate_data.py            # errors fail, warnings are printed
    python scripts/validate_data.py --strict   # warnings fail too (use before deploy)

Cross-file checks: unique ids, cells inside city bounds, no two cells closer
than MIN_CELL_SPACING_KM, every hotspot / relief point belongs to a known city,
sits inside its bounds, has cell_id equal to its nearest cell, and is no more
than MAX_DISTANCE_TO_CELL_KM from it; hotspot sources resolve.
Warnings: missing elevations, unverified entries.
"""

import argparse
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.grid import haversine_km, load_city  # noqa: E402

DATA = ROOT / "data"
SCHEMAS = {"cities": "city", "hotspots": "hotspots", "relief": "relief"}
MIN_CELL_SPACING_KM = 1.0
MAX_DISTANCE_TO_CELL_KM = 6.0


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data_dir: Path = DATA) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    cities = {}

    for folder, schema_name in SCHEMAS.items():
        schema = load_json(data_dir / "schemas" / f"{schema_name}.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        for path in sorted((data_dir / folder).glob("*.json")):
            rel = path.relative_to(data_dir)
            try:
                data = load_json(path)
            except json.JSONDecodeError as e:
                errors.append(f"{rel}: invalid JSON: {e}")
                continue
            schema_errors = list(validator.iter_errors(data))
            for e in schema_errors:
                loc = "/".join(map(str, e.absolute_path)) or "(root)"
                errors.append(f"{rel}: {loc}: {e.message}")
            if schema_errors:
                continue
            if folder == "cities":
                if data["id"] != path.stem:
                    errors.append(f"{rel}: id {data['id']!r} must match file name")
                cities[data["id"]] = data
                errors += check_city(rel, data, warnings)
            else:
                key = "hotspots" if folder == "hotspots" else "points"
                if data["city"] != path.stem:
                    errors.append(f"{rel}: city {data['city']!r} must match file name")
                if data["city"] not in cities:
                    errors.append(f"{rel}: no city file data/cities/{data['city']}.json")
                    continue
                errors += check_points(rel, data, key, data_dir, warnings)
    return errors, warnings


def check_city(rel, city, warnings) -> list[str]:
    errors = []
    b = city["bounds"]
    if not (b["south"] < b["north"] and b["west"] < b["east"]):
        errors.append(f"{rel}: bounds are inverted")
    cells = city["cells"]
    ids = [c["id"] for c in cells]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"{rel}: duplicate cell id {dup!r}")
    for c in cells:
        if not (b["south"] <= c["lat"] <= b["north"] and b["west"] <= c["lon"] <= b["east"]):
            errors.append(f"{rel}: cell {c['id']} is outside the city bounds")
        if c["elevation_m"] is None:
            warnings.append(f"{rel}: cell {c['id']} has no elevation (run scripts/fill_elevation.py)")
    for i, a in enumerate(cells):
        for c in cells[i + 1 :]:
            km = haversine_km(a["lat"], a["lon"], c["lat"], c["lon"])
            if km < MIN_CELL_SPACING_KM:
                errors.append(f"{rel}: cells {a['id']} and {c['id']} are only {km:.2f} km apart")
    if city["ref_elevation_m"] is None:
        warnings.append(f"{rel}: ref_elevation_m is not set")
    return errors


def check_points(rel, data, key, data_dir, warnings) -> list[str]:
    errors = []
    city = load_city(data["city"], data_dir)
    ids = [p["id"] for p in data[key]]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"{rel}: duplicate id {dup!r}")
    source_ids = {s["id"] for s in data.get("sources", [])}
    for p in data[key]:
        where = f"{rel}: {p['id']}"
        if not city.contains(p["lat"], p["lon"]):
            errors.append(f"{where} is outside the city bounds")
        nearest, km = city.nearest(p["lat"], p["lon"])
        if p["cell_id"] is None:
            errors.append(f"{where} has no cell_id (run scripts/assign_cells.py)")
        elif p["cell_id"] != nearest.id:
            errors.append(f"{where} has cell_id {p['cell_id']!r} but its nearest cell is "
                          f"{nearest.id!r} (run scripts/assign_cells.py)")
        if km > MAX_DISTANCE_TO_CELL_KM:
            errors.append(f"{where} is {km:.1f} km from the nearest cell; add a cell nearer to it")
        for s in p.get("sources", []):
            if s not in source_ids:
                errors.append(f"{where} cites unknown source {s!r}")
        if not p["verified"]:
            warnings.append(f"{where} is not verified yet")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.add_argument("--quiet", action="store_true", help="print only a count of warnings")
    args = p.parse_args()

    errors, warnings = validate()
    if args.quiet and warnings:
        print(f"{len(warnings)} warnings (run without --quiet to list them)")
    else:
        for w in warnings:
            print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    failed = bool(errors) or (args.strict and bool(warnings))
    print("FAILED" if failed else "OK", f"({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
