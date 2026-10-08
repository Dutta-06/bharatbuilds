"""collect_history: keep real carbon (and weather) history for model training.

Runs every few hours. Per region: fetch the last 24 h (Electricity Maps history + Open-Meteo),
merge it into s3://<bucket>/history/<region>.csv. Overlapping runs are harmless (union by hour),
so a missed run costs nothing as long as one lands within 24 h.
Sync to a laptop or Colab: aws s3 sync s3://<bucket>/history data/history
"""

import os
from datetime import datetime, timezone

import boto3

from backend import db, history
from model import regions as region_config


def handler(event, context):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    s3 = boto3.client("s3", endpoint_url=db.endpoint_url())
    bucket = os.environ["BUCKET_NAME"]
    summary = {}
    for region in region_config.load().values():
        key = f"history/{region.id}.csv"
        try:
            existing = history.from_csv(s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode())
        except s3.exceptions.NoSuchKey:
            existing = []
        try:
            fresh = history.rows_for(region, 2, now)
        except Exception as e:                         # one region failing must not stop the others
            summary[region.id] = f"failed: {type(e).__name__}: {e}"[:200]
            continue
        merged = history.merge(existing, fresh)
        s3.put_object(Bucket=bucket, Key=key, Body=history.to_csv(merged).encode(), ContentType="text/csv")
        summary[region.id] = {"hours": len(merged), "real_hours": sum(r["ci_source"] != "modelled" for r in merged)}
    print(summary)
    return summary
