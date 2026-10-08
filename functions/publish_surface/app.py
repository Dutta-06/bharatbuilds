"""publish_surface: write the default /surface grids to a public S3 bucket after each forecast run.

The dashboard reads these files for its standard views, so a traffic burst is served by S3
(no Lambda, no cold starts) and this works without a CloudFront distribution. Custom
weights or baselines still go to GET /surface.

Event: ignored.  Return: {"published": ["surface/gpu-hours-1.json", ...]}
"""

import json
import os

import boto3

from backend import surface

GPU_HOURS = (1, 4)       # the values the dashboard asks for with default weights
CACHE_SECONDS = 300


def handler(event, context):
    s3 = boto3.client("s3", endpoint_url=os.environ.get("LOCAL_ENDPOINT_URL") or None)
    published = []
    for hours in GPU_HOURS:
        payload = surface.build({"gpu_hours": str(hours)})
        if payload is None:
            raise RuntimeError("no forecasts stored; nothing to publish")
        key = f"surface/gpu-hours-{hours}.json"
        s3.put_object(Bucket=os.environ["SURFACE_BUCKET"], Key=key, Body=json.dumps(payload).encode(),
                      ContentType="application/json", CacheControl=f"public, max-age={CACHE_SECONDS}")
        published.append(key)
    return {"published": published}
