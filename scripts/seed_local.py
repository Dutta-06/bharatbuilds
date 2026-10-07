"""Run the pipeline (fetch_forecast -> compute_risk) for every cell, locally.

    make seed                         # live Open-Meteo forecasts
    make seed SEED_ARGS=--offline     # synthetic fixture, shifted to today
    make seed SEED_ARGS="--offline --city delhi --cells rohini,okhla"

Writes to whatever AWS_ENDPOINT_URL points at (LocalStack via make).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import cities, risk_store  # noqa: E402
from engine import grid, openmeteo  # noqa: E402

FIXTURE = ROOT / "tests" / "engine" / "fixtures" / "delhi_may_synthetic.json"


def shifted_fixture(today: datetime) -> dict:
    """The synthetic fixture with its dates moved so day 0 is today."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    times = [datetime.fromisoformat(t) for t in raw["hourly"]["time"]]
    day0 = times[0] + timedelta(hours=6)  # fixture starts 6 h before its day 0
    delta = today.replace(hour=0, minute=0) - day0
    raw["hourly"]["time"] = [(t + delta).strftime("%Y-%m-%dT%H:%M") for t in times]
    return raw


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true", help="use the synthetic fixture")
    p.add_argument("--city", action="append", help="city id (default: all)")
    p.add_argument("--cells", help="comma-separated cell ids (default: all)")
    p.add_argument("--pause", type=float, default=0.2, help="seconds between Open-Meteo calls")
    args = p.parse_args()

    if not os.environ.get("AWS_ENDPOINT_URL"):
        sys.exit("AWS_ENDPOINT_URL is not set; refusing to write to a real AWS account. Use `make seed`.")

    total = 0
    for city_id in args.city or grid.city_ids():
        city = cities.city(city_id)
        now = cities.local_now(city.timezone)
        wanted = set(args.cells.split(",")) if args.cells else None
        fixture = shifted_fixture(now) if args.offline else None
        for cell in city.cells:
            if wanted and cell.id not in wanted:
                continue
            if fixture is None:
                raw = openmeteo.fetch_raw(cell.lat, cell.lon)
                time.sleep(args.pause)
            else:
                raw = fixture
            rows, meta = risk_store.compute_rows(city_id, cell.id, raw, now=now)
            total += risk_store.store(rows, meta)
            print(f"{city_id}/{cell.id}: {len(rows)} hours from {meta['first_hour']}")
    print(f"wrote {total} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
