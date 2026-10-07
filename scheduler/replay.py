"""Offline replay: a job queue through the scheduler versus running every job
immediately in its submit region ("naive").

Assumption stated in every output: the scheduler sees the actual weather and
carbon of the replay window (perfect foresight). Real runs use 48 h forecasts,
so this is an upper bound on savings; Step 4's forecast error tells us how far
below it a live system lands.
"""

from __future__ import annotations

import statistics
from dataclasses import replace

from model.cost import Weights

from .greedy import Job, schedule
from .surface import Surface


def replay(jobs: list[Job], surface: Surface) -> dict:
    naive_l = naive_kg = sched_l = sched_kg = 0.0
    delays, moved, infeasible, missed = [], 0, 0, 0
    gpu_h_by_region_naive: dict[str, float] = {}
    gpu_h_by_region_sched: dict[str, float] = {}
    counted = 0
    for job in jobs:
        p = schedule(job, surface, top_k=0)
        if p.baseline is None:      # replay window doesn't cover this job's submit time
            continue
        counted += 1
        naive_l += p.baseline.footprint.litres
        naive_kg += p.baseline.footprint.kg_co2
        gpu_h_by_region_naive[job.submit_region] = gpu_h_by_region_naive.get(job.submit_region, 0) + job.gpu_hours
        chosen = p.chosen if p.feasible else p.baseline   # infeasible -> runs now, here
        if not p.feasible:
            infeasible += 1
        if chosen.end > job.deadline:
            missed += 1
        sched_l += chosen.footprint.litres
        sched_kg += chosen.footprint.kg_co2
        delays.append((chosen.start - p.baseline.start).total_seconds() / 3600)
        moved += chosen.region != job.submit_region
        gpu_h_by_region_sched[chosen.region] = gpu_h_by_region_sched.get(chosen.region, 0) + job.gpu_hours

    def pct(new, old):
        return round(100 * (old - new) / old, 1) + 0.0 if old else None

    return {
        "jobs": counted,
        "naive": {"litres": round(naive_l, 1), "kg_co2": round(naive_kg, 2)},
        "pravaah": {"litres": round(sched_l, 1), "kg_co2": round(sched_kg, 2)},
        "saved_pct": {"litres": pct(sched_l, naive_l), "kg_co2": pct(sched_kg, naive_kg)},
        "deadline_hit_rate_pct": round(100 * (counted - missed) / counted, 1) if counted else None,
        "infeasible_ran_now": infeasible,
        "median_delay_h": round(statistics.median(delays), 1) if delays else None,
        "moved_region_pct": round(100 * moved / counted, 1) if counted else None,
        "gpu_hours_by_region": {"naive": _round(gpu_h_by_region_naive), "pravaah": _round(gpu_h_by_region_sched)},
    }


def _round(d: dict) -> dict:
    return {k: round(v, 1) for k, v in sorted(d.items())}


def with_slack(jobs: list[Job], extra_h: float) -> list[Job]:
    """Each job gets exactly its duration + extra_h of slack (sensitivity to deadlines)."""
    from datetime import timedelta

    return [replace(j, deadline=j.submit_time + timedelta(hours=j.duration_h + extra_h)) for j in jobs]


def with_weights(jobs: list[Job], weights: Weights) -> list[Job]:
    return [replace(j, weights=weights) for j in jobs]


def stay_home(jobs: list[Job]) -> list[Job]:
    """Time-shifting only: every job stays in its submit region (separates 'when' from 'where')."""
    return [replace(j, allowed_regions=(j.submit_region,)) for j in jobs]
