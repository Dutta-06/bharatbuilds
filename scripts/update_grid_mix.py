"""Replace the placeholder grid mix and typical carbon intensity in data/regions.yaml with real data.

    aws s3 sync s3://<BucketName>/history data/history      # real Electricity Maps hours saved by collect_history
    python scripts/update_grid_mix.py --dry-run             # show what would change
    python scripts/update_grid_mix.py                       # write it

For each region it takes the hours in data/history/<region>.csv whose carbon source is not "modelled", sums the
generation by source (megawatts, so big hours count more, as in an annual mix) and writes the shares and the mean
carbon intensity. The comment on each line records the window, so nobody mistakes it for an annual figure.
The mix is only a fallback (live hourly mixes override it), but it is what the cost model uses when one is missing.
For a true annual mix, use Electricity Maps' data portal or Ember's yearly data instead and edit the file by hand.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ROOT / "data" / "regions.yaml"
HISTORY = ROOT / "data" / "history"


def summarise(rows: list[dict]) -> dict | None:
    """Mean mix (shares summing to 1) and mean intensity over real hours, or None if there are none."""
    real = [r for r in rows if r["ci_source"] != "modelled"]
    if not real:
        return None
    total: Counter = Counter()
    for r in real:
        for source, mw in json.loads(r["mix_json"]).items():
            if mw and mw > 0:
                total[source] += mw
    whole = sum(total.values())
    if whole <= 0:
        return None
    shares = {k: round(v / whole, 3) for k, v in total.most_common() if round(v / whole, 3) > 0}
    drift = round(1 - sum(shares.values()), 3)
    top = next(iter(shares))
    shares[top] = round(shares[top] + drift, 3)             # rounding leftovers go to the largest source
    hours = sorted(r["hour"] for r in real)
    return {"shares": shares, "ci": round(sum(float(r["ci_g_per_kwh"]) for r in real) / len(real)),
            "hours": len(real), "first": hours[0], "last": hours[-1]}


def apply(text: str, region: str, s: dict) -> str:
    block = re.search(rf"(^  - id: {re.escape(region)}\n)(.*?)(?=^  - id: |\Z)", text, flags=re.M | re.S)
    if not block:
        raise ValueError(f"no region {region} in regions.yaml")
    shares = ", ".join(f"{k}: {v:g}" for k, v in s["shares"].items())
    window = f"mean of {s['hours']} real Electricity Maps hours, {s['first'][:10]} to {s['last'][:10]}; not an annual figure"
    body = block.group(2)
    body, n1 = re.subn(r"^    grid_mix:.*$", f"    grid_mix: {{placeholder: false, shares: {{{shares}}}}}   # {window}", body, flags=re.M)
    body, n2 = re.subn(r"^    typical_ci_g_per_kwh:.*$", f"    typical_ci_g_per_kwh: {s['ci']}            # same window", body, flags=re.M)
    if n1 != 1 or n2 != 1:
        raise ValueError(f"{region}: expected one grid_mix and one typical_ci_g_per_kwh line")
    return text[:block.start(2)] + body + text[block.end(2):]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--min-days", type=float, default=7, help="refuse regions with fewer real days than this")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    text = REGIONS.read_text(encoding="utf-8")
    ids = re.findall(r"^  - id: (\S+)$", text, flags=re.M)
    problems = 0
    for rid in ids:
        path = HISTORY / f"{rid}.csv"
        if not path.exists():
            print(f"{rid:16} no {path.relative_to(ROOT)}; run aws s3 sync first", file=sys.stderr); problems += 1; continue
        with path.open(newline="", encoding="utf-8") as f:
            s = summarise(list(csv.DictReader(f)))
        if s is None or s["hours"] < args.min_days * 24:
            have = 0 if s is None else s["hours"] / 24
            print(f"{rid:16} only {have:.1f} real days, need {args.min_days:g}; left unchanged", file=sys.stderr); problems += 1; continue
        print(f"{rid:16} {s['hours']:4d} h  ci {s['ci']:4d}  " + ", ".join(f"{k} {v:.0%}" for k, v in list(s["shares"].items())[:4]))
        text = apply(text, rid, s)
    if not args.dry_run and problems == 0:
        REGIONS.write_text(text, encoding="utf-8")
        print("updated data/regions.yaml; now run: make validate && make test")
    elif problems:
        print("nothing written: fix the regions above first (or lower --min-days)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
