"""Validate model/coefficients.yaml and data/regions.yaml.

    python scripts/validate_data.py            # errors fail; unchecked sources are warnings
    python scripts/validate_data.py --strict   # warnings fail too (use before the demo)

Rules: every coefficient has a value, unit, uncertainty, a source with an https/http
URL, and a `checked` flag; every region references a known cooling type, a
disclosed-WUE key that exists, and a grid mix of known sources summing to ~1.
"""

import argparse
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model.water import COOLING_TYPES  # noqa: E402

SOURCE = {
    "type": "object",
    "required": ["title", "url"],
    "properties": {"title": {"type": "string", "minLength": 3},
                   "url": {"type": "string", "pattern": "^https?://"}},
    "additionalProperties": False,
}

REGIONS_SCHEMA = {
    "type": "object",
    "required": ["regions"],
    "properties": {"regions": {"type": "array", "minItems": 1, "items": {
        "type": "object",
        "required": ["id", "name", "lat", "lon", "cooling_type", "electricity_maps_zone",
                     "water_stress_score", "grid_mix"],
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z]{2}(-[a-z]+)+-[0-9]$"},
            "name": {"type": "string"},
            "lat": {"type": "number", "minimum": -90, "maximum": 90},
            "lon": {"type": "number", "minimum": -180, "maximum": 180},
            "cooling_type": {"enum": list(COOLING_TYPES)},
            "electricity_maps_zone": {"type": ["string", "null"]},
            "disclosed_wue_key": {"type": "string"},
            "pue": {"type": "number", "minimum": 1.0, "maximum": 3.0},
            "water_stress_score": {"type": ["number", "null"], "minimum": 0, "maximum": 5},
            "wue_scale": {"type": "number", "exclusiveMinimum": 0},
            "typical_ci_g_per_kwh": {"type": "number", "minimum": 0},
            "grid_mix": {"type": "object", "required": ["shares"], "properties": {
                "placeholder": {"type": "boolean"},
                "shares": {"type": "object", "additionalProperties": {"type": "number", "minimum": 0}},
            }, "additionalProperties": False},
        },
        "additionalProperties": False,
    }}},
    "additionalProperties": False,
}


def walk_coefficients(node, path, errors, warnings):
    """Any dict with a `value` or `values` key is a coefficient and must be documented."""
    if not isinstance(node, dict):
        return
    if "value" in node or "values" in node:
        where = ".".join(path)
        is_flag = isinstance(node.get("value"), bool)
        required = ["note"] if is_flag else ["unit", "uncertainty", "source", "checked"]
        # Grouped coefficients (`values`) may inherit source/unit from their parent block.
        for key in required:
            if key not in node:
                errors.append(f"coefficients: {where} is missing `{key}`")
        if "source" in node:
            try:
                jsonschema.validate(node["source"], SOURCE)
            except jsonschema.ValidationError as e:
                errors.append(f"coefficients: {where}.source: {e.message}")
        if "uncertainty" in node and not (0 <= float(node["uncertainty"]) <= 2):
            errors.append(f"coefficients: {where}.uncertainty must be between 0 and 2")
        if node.get("checked") is False:
            warnings.append(f"coefficients: {where} not checked against its source yet")
        return
    for key, child in node.items():
        walk_coefficients(child, path + [key], errors, warnings)


def validate(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    coeffs = yaml.safe_load((root / "model" / "coefficients.yaml").read_text(encoding="utf-8"))
    walk_coefficients(coeffs, [], errors, warnings)

    grid_sources = set(coeffs["grid_water_factors"]["values"])
    wue_keys = set(coeffs["regional_wue"]["values"])

    regions = yaml.safe_load((root / "data" / "regions.yaml").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(regions, REGIONS_SCHEMA)
    except jsonschema.ValidationError as e:
        loc = "/".join(map(str, e.absolute_path)) or "(root)"
        return errors + [f"regions: {loc}: {e.message}"], warnings

    ids = [r["id"] for r in regions["regions"]]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"regions: duplicate id {dup}")
    for r in regions["regions"]:
        rid = r["id"]
        key = r.get("disclosed_wue_key", rid)
        if key not in wue_keys:
            if "disclosed_wue_key" in r:
                errors.append(f"regions: {rid} disclosed_wue_key {key!r} is not in coefficients regional_wue")
            else:
                warnings.append(f"regions: {rid} has no disclosed WUE; its site curve stays uncalibrated")
        shares = r["grid_mix"]["shares"]
        unknown = set(shares) - grid_sources
        if unknown:
            errors.append(f"regions: {rid} grid_mix has unknown sources {sorted(unknown)}")
        total = sum(shares.values())
        if shares and abs(total - 1.0) > 0.02:
            errors.append(f"regions: {rid} grid_mix shares sum to {total:.2f}, not 1")
        if r["grid_mix"].get("placeholder"):
            warnings.append(f"regions: {rid} grid_mix is a placeholder")
        if r["water_stress_score"] is None:
            warnings.append(f"regions: {rid} has no Aqueduct water stress score yet")
        if "wue_scale" not in r and key in wue_keys and r["cooling_type"] != "air":
            warnings.append(f"regions: {rid} not calibrated (run scripts/calibrate_wue.py)")
    return errors, warnings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    errors, warnings = validate()
    if args.quiet and warnings:
        print(f"{len(warnings)} warnings (run without --quiet to list)")
    else:
        for w in warnings:
            print("warning:", w)
    for e in errors:
        print("error:", e)
    failed = bool(errors) or (args.strict and bool(warnings))
    print("FAILED" if failed else "OK", f"({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
