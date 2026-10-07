"""CLI: print a 48-hour risk strip for a point.

    python -m engine --lat 28.7 --lon 77.1 --work heavy
    python -m engine --lat 28.7 --lon 77.1 --work heavy --lang hi --hazard waterlogging
    python -m engine --city delhi --cell rohini --work heavy
    python -m engine --from-file tests/engine/fixtures/delhi_may_synthetic.json --now 2026-05-26T06:00
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from . import grid, openmeteo
from .risk import assess
from .thresholds import WORK_INTENSITIES
from .windows import HAZARDS, languages

BLOCKS = {"green": "\033[42m", "amber": "\033[43m", "red": "\033[41m"}
PLAIN = {"green": "G", "amber": "A", "red": "R"}
RESET = "\033[0m"
DELHI_REF_ELEVATION_M = 216.0


def render_strip(strip: list[dict], color: bool) -> str:
    """Two rows: hour labels and coloured blocks, in 24-hour chunks."""
    lines = []
    for day in range(0, len(strip), 24):
        chunk = strip[day : day + 24]
        lines.append(" ".join(f"{s['time'][11:13]}" for s in chunk))
        if color:
            lines.append(" ".join(f"{BLOCKS[s['level']]}  {RESET}" for s in chunk))
        else:
            lines.append(" ".join(f"{PLAIN[s['level']]} " for s in chunk))
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine", description=__doc__.split("\n")[0])
    p.add_argument("--lat", type=float, default=28.7)
    p.add_argument("--lon", type=float, default=77.1)
    p.add_argument("--work", choices=WORK_INTENSITIES, default="heavy")
    p.add_argument("--lang", choices=languages(), default="en")
    p.add_argument("--hazard", choices=HAZARDS + ("all",), default="all")
    p.add_argument("--city", help="city id from data/cities (enables --cell and hotspot lookup)")
    p.add_argument("--cell", help="cell id within --city; overrides --lat/--lon")
    p.add_argument("--hotspot", action="store_true", help="treat the point as a waterlogging hotspot")
    p.add_argument("--ref-elevation", type=float, default=DELHI_REF_ELEVATION_M,
                   help="city reference elevation in m (default: Delhi)")
    p.add_argument("--unacclimatised", action="store_true")
    p.add_argument("--from-file", help="read an Open-Meteo JSON response instead of calling the API")
    p.add_argument("--now", help="local ISO time to start the strip at (default: current hour)")
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)

    cell = None
    if args.city:
        city = grid.load_city(args.city)
        if args.cell:
            try:
                cell = city.cell(args.cell)
            except KeyError:
                p.error(f"no cell {args.cell!r} in {args.city}; one of: "
                        + ", ".join(c.id for c in city.cells))
        else:
            cell, _ = city.nearest(args.lat, args.lon)
        args.lat, args.lon = cell.lat, cell.lon
        args.hotspot = args.hotspot or cell.id in grid.hotspot_cells(args.city)
        if city.ref_elevation_m is not None:
            args.ref_elevation = city.ref_elevation_m
    elif args.cell:
        p.error("--cell needs --city")

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            forecast = openmeteo.parse(json.load(f))
    else:
        try:
            forecast = openmeteo.fetch(args.lat, args.lon)
        except OSError as e:
            print(f"Could not reach Open-Meteo: {e}", file=sys.stderr)
            return 1

    result = assess(
        forecast,
        work=args.work,
        lang=args.lang,
        has_hotspot=args.hotspot,
        city_ref_elevation_m=args.ref_elevation,
        acclimatised=not args.unacclimatised,
        now=datetime.fromisoformat(args.now) if args.now else None,
        elevation_m=cell.elevation_m if cell else None,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    color = not args.no_color and sys.stdout.isatty()
    hazards = HAZARDS if args.hazard == "all" else (args.hazard,)
    place = f"{cell.name} ({cell.name_hi})" if cell else f"{forecast.latitude}, {forecast.longitude}"
    hotspot = " · waterlogging hotspot" if args.hotspot else ""
    elevation = cell.elevation_m if cell and cell.elevation_m is not None else forecast.elevation
    print(f"{place} · elevation {elevation} m{hotspot} · {args.work} work\n")
    for hazard in hazards:
        h = result["hazards"][hazard]
        print(f"== {hazard} · now: {h['now_word']} ==")
        print(render_strip(h["strip"], color))
        for sentence in h["sentences"]:
            print(sentence)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
