"""Step 14: hammer a read endpoint with N concurrent requests and report latency.

    python scripts/load_test.py https://<cloudfront>/surface?gpu_hours=4 --concurrency 200 --requests 1000

Run it against the CloudFront URL (ApiUrl output), not the API Gateway origin: the point
is to confirm the 5-minute cache absorbs the burst. Look for x-cache: Hit from cloudfront.
"""

import argparse
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def one(url: str) -> tuple[int, float, str]:
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pravaah-load"}), timeout=30) as r:
            r.read()
            return r.status, time.perf_counter() - t, r.headers.get("x-cache", "")
    except Exception as e:  # count failures instead of dying
        return getattr(e, "code", 0) or 0, time.perf_counter() - t, type(e).__name__


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--concurrency", type=int, default=200)
    p.add_argument("--requests", type=int, default=1000)
    args = p.parse_args()
    start = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool:
        results = list(pool.map(one, [args.url] * args.requests))
    wall = time.perf_counter() - start
    ok = [r for r in results if r[0] == 200]
    lat = sorted(r[1] * 1000 for r in ok) or [0]
    hits = sum("Hit" in r[2] for r in results)
    print(f"{len(results)} requests, {args.concurrency} concurrent, {wall:.1f} s -> {len(results) / wall:.0f} req/s")
    print(f"200 OK: {len(ok)}  errors: {len(results) - len(ok)}  CloudFront hits: {hits}")
    print(f"latency ms  p50 {statistics.median(lat):.0f}  p90 {lat[int(0.9 * (len(lat) - 1))]:.0f}  "
          f"p99 {lat[int(0.99 * (len(lat) - 1))]:.0f}  max {lat[-1]:.0f}")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
