"""Pull weather and grid history for every region into data/history/<region>.csv.

    python scripts/pull_history.py --days 60
    python scripts/pull_history.py --days 60 --regions ap-south-1,eu-north-1
    python scripts/pull_history.py --days 60 --s3 s3://<bucket>/history/   # also upload (needs boto3)

Columns: hour (UTC), t_db, rh, p_hpa, t_wb, ci_g_per_kwh, ci_source, mix_json.

Weather comes from Open-Meteo (forecast endpoint's past_days up to 92 days, so
it reaches the current hour; the archive beyond that). Carbon comes from Electricity Maps
when ELECTRICITYMAPS_TOKEN is set. The free tier only returns the last 24 h, so
older hours fall back to the modelled profile and say so in ci_source. The hourly
pipeline (Step 5) stores every run, so real history accumulates from deploy day.

Writes Parquet as well if pyarrow is installed (pip install pyarrow).
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.history import COLUMNS, rows_for  # noqa: E402
from model import regions as region_config  # noqa: E402

OUT = ROOT / "data" / "history"


def write(region_id: str, rows: list[dict]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{region_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist(rows), path.with_suffix(".parquet"))
    except ImportError:
        pass
    return path


def upload(paths: list[Path], s3_url: str) -> None:
    import boto3

    bucket, _, prefix = s3_url.removeprefix("s3://").partition("/")
    s3 = boto3.client("s3")
    for p in paths:
        for f in (p, p.with_suffix(".parquet")):
            if f.exists():
                s3.upload_file(str(f), bucket, f"{prefix.rstrip('/')}/{f.name}".lstrip("/"))
                print(f"uploaded s3://{bucket}/{prefix.rstrip('/')}/{f.name}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--regions", help="comma-separated region ids (default: all)")
    p.add_argument("--s3", help="s3://bucket/prefix/ to upload to")
    args = p.parse_args()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    wanted = set(args.regions.split(",")) if args.regions else None
    written = []
    for region in region_config.load().values():
        if wanted and region.id not in wanted:
            continue
        rows = rows_for(region, args.days, now)
        real = sum(r["ci_source"] != "modelled" for r in rows)
        path = write(region.id, rows)
        written.append(path)
        print(f"{region.id:16} {len(rows):5} h  ({rows[0]['hour']} .. {rows[-1]['hour']}), "
              f"{real} h of real carbon data -> {path.relative_to(ROOT)}")
    if args.s3:
        upload(written, args.s3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
