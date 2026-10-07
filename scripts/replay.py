"""Replay a job trace through the scheduler: naive (run now, in the submit region)
versus Pravaah. Writes dashboard/public/replay.json for the Savings page.

    python scripts/replay.py                       # synthetic trace, history if present else synthetic weather
    python scripts/replay.py --trace data/trace.csv
    python scripts/replay.py --weather synthetic   # force synthetic weather + modelled carbon

Weather/carbon: data/history/<region>.csv (scripts/pull_history.py) when every
region has it, else synthetic weather with the modelled carbon profile. The output
names which was used, and the trace source, so no chart can hide it.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import regions as region_config  # noqa: E402
from model.cost import Conditions, Weights  # noqa: E402
from scheduler import trace  # noqa: E402
from scheduler.replay import replay, stay_home, with_slack, with_weights  # noqa: E402
from scheduler.surface import build  # noqa: E402
from sources import synthetic  # noqa: E402
from sources.carbon import ModelledProfile  # noqa: E402

OUT = ROOT / "dashboard" / "public" / "replay.json"
SLACKS = [0, 4, 12, 24, 48]


def history_conditions(regions) -> tuple[dict, datetime] | None:
    out, starts, ends = {}, [], []
    for rid in regions:
        path = ROOT / "data" / "history" / f"{rid}.csv"
        if not path.exists():
            return None
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        out[rid] = [Conditions(r["hour"], float(r["t_db"]), max(1.0, float(r["rh"])), float(r["ci_g_per_kwh"]),
                               float(r["p_hpa"]), json.loads(r["mix_json"]) or None) for r in rows]
        starts.append(rows[0]["hour"])
        ends.append(rows[-1]["hour"])
    return out, datetime.strptime(max(starts), "%Y-%m-%dT%H:00")


def synthetic_conditions(regions, start: datetime, hours: int) -> dict:
    out = {}
    for rid, r in regions.items():
        profile = ModelledProfile(r.typical_ci_g_per_kwh or 0.0, r.grid_mix, r.lon)
        out[rid] = [Conditions(t, temp, rh, profile.at(datetime.strptime(t, "%Y-%m-%dT%H:00")).ci_g_per_kwh, p)
                    for t, temp, rh, p in synthetic.weather(rid, start, hours)]
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trace", type=Path, default=ROOT / "data" / "trace.synthetic.csv")
    p.add_argument("--weather", choices=["auto", "history", "synthetic"], default="auto")
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()

    regions = region_config.load()
    hist = None if args.weather == "synthetic" else history_conditions(regions)
    if args.weather == "history" and hist is None:
        sys.exit("no data/history for every region; run scripts/pull_history.py")
    if hist:
        conds, start = hist
        weather_source = "history (data/history; carbon source per row)"
    else:
        start = datetime(2026, 10, 5)
        conds = synthetic_conditions(regions, start, 24 * 10)
        weather_source = "synthetic weather + modelled carbon (no history pulled yet)"

    surface = build(regions, conds)
    jobs = trace.load(args.trace, start)
    with args.trace.open(newline="", encoding="utf-8") as f:
        trace_source = sorted({row["source"] for row in csv.DictReader(f)})

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "assumptions": [
            "Perfect foresight: the scheduler sees the replay window's actual weather and carbon (an upper bound).",
            "Naive = every job runs immediately in the region it was submitted from.",
            f"Trace: {', '.join(trace_source)} ({args.trace.name}); deadlines are synthetic slack, regions assigned uniformly.",
            f"Weather and carbon: {weather_source}.",
            "Site water uses physics curves; uncalibrated regions overstate absolute litres (see HUMAN-TODO).",
        ],
        "trace_source": trace_source,
        "weather_source": weather_source,
        "headline": replay(jobs, surface),
        "when_vs_where": {
            "time_only_same_region": _short(replay(stay_home(jobs), surface)),
            "time_and_region": _short(replay(jobs, surface)),
        },
        "slack_sensitivity": [{"extra_slack_h": s, **_short(replay(with_slack(jobs, s), surface))} for s in SLACKS],
        "weight_sensitivity": [
            {"weights": name, **_short(replay(with_weights(jobs, w), surface))}
            for name, w in [("water only", Weights(1, 0)), ("balanced", Weights(0.5, 0.5)), ("carbon only", Weights(0, 1))]
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    h = result["headline"]
    print(f"{h['jobs']} jobs | water {h['naive']['litres']} -> {h['pravaah']['litres']} L ({h['saved_pct']['litres']}% less) | "
          f"CO2 {h['naive']['kg_co2']} -> {h['pravaah']['kg_co2']} kg ({h['saved_pct']['kg_co2']}% less) | "
          f"deadlines met {h['deadline_hit_rate_pct']}% | median delay {h['median_delay_h']} h | moved {h['moved_region_pct']}%")
    t = result["when_vs_where"]["time_only_same_region"]["saved_pct"]
    print(f"  time-shift only (same region): water {t['litres']}%, CO2 {t['kg_co2']}%")
    for row in result["slack_sensitivity"]:
        print(f"  slack +{row['extra_slack_h']:>2} h: water {row['saved_pct']['litres']}%, CO2 {row['saved_pct']['kg_co2']}%")
    for row in result["weight_sensitivity"]:
        print(f"  {row['weights']:12}: water {row['saved_pct']['litres']}%, CO2 {row['saved_pct']['kg_co2']}%")
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    return 0


def _short(r: dict) -> dict:
    return {"saved_pct": r["saved_pct"], "median_delay_h": r["median_delay_h"], "moved_region_pct": r["moved_region_pct"]}


if __name__ == "__main__":
    sys.exit(main())
