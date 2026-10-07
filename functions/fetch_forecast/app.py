"""fetch_forecast: 48 h of weather + grid for one region; raw copy to S3.

Event:  {"region": "ap-south-1", "offline": false}
Return: {"region", "rows": [...48 hourly rows...], "raw_key"}
"""

import json
import os
from datetime import datetime, timezone

import boto3

from backend import db, forecasts


def handler(event, context):
    region = event["region"]
    offline = bool(event.get("offline", forecasts.offline_default()))
    rows = forecasts.collect(region, offline=offline)
    raw_key = None
    bucket = os.environ.get("BUCKET_NAME")
    if bucket and not event.get("skip_s3"):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
        raw_key = f"raw/forecast/{region}/{stamp}.json"
        boto3.client("s3", endpoint_url=db.endpoint_url()).put_object(
            Bucket=bucket, Key=raw_key, Body=json.dumps(rows).encode(), ContentType="application/json")
    return {"region": region, "rows": rows, "raw_key": raw_key}
