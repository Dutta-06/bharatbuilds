"""Build a job queue for replay (Step 10) from a public GPU cluster trace.

Real trace (preferred): Alibaba cluster-trace-gpu-v2020, pai_task_table.csv
(https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020).
Download it, then:

    python scripts/sample_trace.py --alibaba path/to/pai_task_table.csv --n 500

Synthetic fallback (clearly labelled; used until the real one is sampled):

    python scripts/sample_trace.py --synthetic --n 500

Output columns: job_id, submit_offset_h, gpu_hours, gpus, slack_h, submit_region, source

Assumptions, stated because the trace cannot supply them:
- Deadlines: the trace has none. slack_h (deadline minus submit) is
  duration + one of 4/12/24/48 h, weighted 0.2/0.3/0.3/0.2. Step 10 varies this.
- Regions: the trace is one cluster. Jobs get a submit region uniformly at random
  across data/regions.yaml.
- Only finished GPU tasks of 15 min to 200 GPU-hours are kept (long, flexible work).
"""

import argparse
import csv
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import regions as region_config  # noqa: E402

ALIBABA_COLUMNS = ["job_name", "task_name", "inst_num", "status", "start_time", "end_time",
                   "plan_cpu", "plan_mem", "plan_gpu", "gpu_type"]
SLACK_EXTRA_H = [(4, 0.2), (12, 0.3), (24, 0.3), (48, 0.2)]
OUT_COLUMNS = ["job_id", "submit_offset_h", "gpu_hours", "gpus", "slack_h", "submit_region", "source"]


def pick(rng: random.Random, weighted):
    r, acc = rng.random(), 0.0
    for value, w in weighted:
        acc += w
        if r <= acc:
            return value
    return weighted[-1][0]


def slack_for(duration_h: float, rng: random.Random) -> float:
    return math.ceil(duration_h) + pick(rng, SLACK_EXTRA_H)


def from_alibaba(path: Path, n: int, rng: random.Random, regions: list[str]) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        first = f.readline()
        f.seek(0)
        reader = csv.DictReader(f) if "job_name" in first else csv.DictReader(f, fieldnames=ALIBABA_COLUMNS)
        tasks = []
        for row in reader:
            try:
                if row["status"] != "Terminated" or not row["plan_gpu"]:
                    continue
                start, end = float(row["start_time"]), float(row["end_time"])
                gpus_per_inst = float(row["plan_gpu"]) / 100.0       # 100 = one whole GPU
                inst = int(float(row["inst_num"] or 1))
            except (ValueError, KeyError):
                continue
            hours = (end - start) / 3600.0
            gpus = max(1, round(gpus_per_inst * inst))
            gpu_hours = gpus_per_inst * inst * hours
            if hours >= 0.25 and 0 < gpu_hours <= 200:
                tasks.append((start, gpu_hours, gpus, row["job_name"]))
    if not tasks:
        raise SystemExit("no usable tasks found; check the file and its columns")
    sample = rng.sample(tasks, min(n, len(tasks)))
    t0 = min(t[0] for t in sample)
    out = []
    for start, gpu_hours, gpus, name in sorted(sample):
        duration = gpu_hours / gpus
        out.append({
            "job_id": f"ali-{name[:12]}", "submit_offset_h": round((start - t0) / 3600.0, 2),
            "gpu_hours": round(gpu_hours, 2), "gpus": gpus, "slack_h": slack_for(duration, rng),
            "submit_region": rng.choice(regions), "source": "alibaba-gpu-v2020",
        })
    return out


def synthetic(n: int, rng: random.Random, regions: list[str], days: int = 7) -> list[dict]:
    """A plausible week-long queue: lognormal GPU-hours, office-hours submit peak."""
    out = []
    for i in range(n):
        while True:  # rejection-sample submit times with a daytime bump
            t = rng.uniform(0, days * 24)
            if rng.random() < 0.4 + 0.6 * max(0.0, math.sin((t % 24 - 6) / 12 * math.pi)):
                break
        gpus = pick(rng, [(1, 0.6), (2, 0.15), (4, 0.15), (8, 0.1)])
        gpu_hours = min(200.0, max(0.25, rng.lognormvariate(math.log(2.0 * gpus), 1.0)))
        out.append({
            "job_id": f"syn-{i:04d}", "submit_offset_h": round(t, 2), "gpu_hours": round(gpu_hours, 2),
            "gpus": gpus, "slack_h": slack_for(gpu_hours / gpus, rng),
            "submit_region": rng.choice(regions), "source": "synthetic",
        })
    return sorted(out, key=lambda r: r["submit_offset_h"])


def main() -> int:
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--alibaba", type=Path, help="path to pai_task_table.csv")
    src.add_argument("--synthetic", action="store_true")
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path)
    args = p.parse_args()

    rng = random.Random(args.seed)
    regions = sorted(region_config.load())
    rows = from_alibaba(args.alibaba, args.n, rng, regions) if args.alibaba else synthetic(args.n, rng, regions)
    out = args.out or ROOT / "data" / ("trace.synthetic.csv" if args.synthetic else "trace.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    total = sum(r["gpu_hours"] for r in rows)
    print(f"wrote {len(rows)} jobs, {total:.0f} GPU-hours, to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
