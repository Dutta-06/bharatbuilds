"""Fill elevation_m for every cell from the Open-Meteo elevation API (run once per city).

Also sets ref_elevation_m to the median cell elevation, which the waterlogging
model uses to decide whether a cell is low-lying.

    python scripts/fill_elevation.py delhi
    python scripts/fill_elevation.py delhi --force   # overwrite existing values
"""

import argparse
import json
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _jsonio import dump, load  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
URL = "https://api.open-meteo.com/v1/elevation"
BATCH = 100  # API limit per request


def fetch(lats: list[float], lons: list[float]) -> list[float]:
    q = urllib.parse.urlencode({"latitude": ",".join(map(str, lats)),
                                "longitude": ",".join(map(str, lons))})
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": "chhaanv/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["elevation"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("city")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    path = DATA_DIR / "cities" / f"{args.city}.json"
    city = load(path)
    todo = [c for c in city["cells"] if args.force or c["elevation_m"] is None]
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        for cell, elev in zip(chunk, fetch([c["lat"] for c in chunk], [c["lon"] for c in chunk])):
            cell["elevation_m"] = round(float(elev), 1)
    city["ref_elevation_m"] = statistics.median(c["elevation_m"] for c in city["cells"])
    dump(city, path)
    print(f"{args.city}: filled {len(todo)} cells, ref_elevation_m = {city['ref_elevation_m']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
