"""Run the forecast pipeline (fetch -> store) for every region, locally.

    make seed                        # live Open-Meteo (+ Electricity Maps if ELECTRICITYMAPS_TOKEN)
    make seed SEED_ARGS=--offline    # synthetic weather and modelled carbon, no internet

Writes to whatever AWS_ENDPOINT_URL points at (LocalStack via make).
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import forecasts  # noqa: E402
from model import regions  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true")
    p.add_argument("--regions", help="comma-separated (default: all)")
    args = p.parse_args()
    if not os.environ.get("AWS_ENDPOINT_URL"):
        sys.exit("AWS_ENDPOINT_URL is not set; refusing to write to a real AWS account. Use `make seed`.")
    wanted = args.regions.split(",") if args.regions else list(regions.load())
    for rid in wanted:
        rows = forecasts.collect(rid, offline=args.offline)
        meta = forecasts.store(rid, rows)
        print(f"{rid:16} {meta['hours']} h from {meta['first_hour']}  "
              f"weather={','.join(meta['weather_sources'])} carbon={','.join(meta['ci_sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
