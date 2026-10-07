"""Calibrate each region's site-WUE curve to its disclosed annual WUE.

For every region with a disclosed WUE, pull a year of hourly weather from the
Open-Meteo archive, run the physics curve for the region's cooling type over it,
and write wue_scale = disclosed / modelled annual mean into data/regions.yaml.

    python scripts/calibrate_wue.py              # all regions
    python scripts/calibrate_wue.py ap-south-1   # one region
    python scripts/calibrate_wue.py --dry-run    # print, do not write

Needs network access to archive-api.open-meteo.com.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import regions  # noqa: E402
from sources import openmeteo  # noqa: E402
from model.water import calibration_factor, wue_site_physics  # noqa: E402
from model.wetbulb import wet_bulb  # noqa: E402


def modelled(region) -> tuple[float, list[tuple[float, float]]]:
    start, end = openmeteo.last_full_year()
    hours = openmeteo.history(region.lat, region.lon, start, end)
    weather = [(wet_bulb(t, rh, p), t) for _, t, rh, p in hours]
    mean = sum(wue_site_physics(wb, db, region.cooling_type) for wb, db in weather) / len(weather)
    return mean, weather


def write_scale(path: Path, region_id: str, scale: float) -> None:
    """Set or replace `wue_scale:` inside the region's block, keeping comments intact."""
    text = path.read_text(encoding="utf-8")
    marker = f"  - id: {region_id}\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"region {region_id} not found in {path}")
    nxt = text.find("\n  - id: ", start + len(marker))
    end = len(text) if nxt < 0 else nxt + 1
    lines = [ln for ln in text[start:end].rstrip("\n").split("\n") if not ln.startswith("    wue_scale:")]
    block = "\n".join(lines) + f"\n    wue_scale: {scale:.4f}\n" + ("" if nxt < 0 else "\n")
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("regions", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    for region in regions.load().values():
        if args.regions and region.id not in args.regions:
            continue
        if region.disclosed_wue is None or region.cooling_type == "air":
            print(f"{region.id:16} skipped (no disclosed WUE or air-cooled)")
            continue
        mean, weather = modelled(region)
        scale = calibration_factor(weather, region.cooling_type, region.disclosed_wue)
        print(f"{region.id:16} {region.cooling_type:10} modelled {mean:5.2f} L/kWh, "
              f"disclosed {region.disclosed_wue:5.2f} -> scale {scale:.3f} ({len(weather)} h)")
        if not args.dry_run:
            write_scale(regions.PATH, region.id, scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
