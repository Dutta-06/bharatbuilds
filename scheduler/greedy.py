"""Greedy placement: the cheapest (region, start hour) that finishes by the deadline.

A job runs for ``duration_h = ceil(gpu_hours / gpus)`` whole hours on one
region. Candidate starts are every whole hour from the submit hour while

    start + duration_h <= deadline        (finish in time)
    start - submit     <= max_delay_h     (if set)
    region allowed, and in the submit region's geo if data_residency is set
    the forecast covers every hour of the window

Each candidate is costed with model.cost.cost, normalised to the baseline
(run now, in the submit region), so cost 1.0 = "no better than now".
The cheapest wins; ties go to the earliest start, then to the submit region.
Alternatives are the best slot in each other region (up to three).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from model.cost import Footprint, Weights, cost
from model.energy import job_it_kwh

from .surface import Surface, hour_key


@dataclass(frozen=True)
class Job:
    id: str
    gpu_hours: float
    submit_time: datetime          # UTC, naive
    deadline: datetime             # UTC, naive; the job must finish by then
    submit_region: str
    gpus: int = 1
    gpu: str = "a100"
    allowed_regions: tuple[str, ...] | None = None   # None = all regions in the surface
    data_residency: bool = False
    max_delay_h: float | None = None
    weights: Weights = field(default_factory=Weights)

    @property
    def duration_h(self) -> int:
        return max(1, math.ceil(self.gpu_hours / self.gpus - 1e-9))

    @property
    def it_kwh(self) -> float:
        return job_it_kwh(self.gpu_hours, self.gpu)


@dataclass(frozen=True)
class Option:
    region: str
    start: datetime
    end: datetime
    cost: float
    footprint: Footprint

    def as_dict(self, submit_time: datetime | None = None) -> dict:
        d = {
            "region": self.region,
            "start": hour_key(self.start),
            "end": hour_key(self.end),
            "cost": round(self.cost, 4),
            "litres": round(self.footprint.litres, 3),
            "litres_low": round(self.footprint.litres_low, 3),
            "litres_high": round(self.footprint.litres_high, 3),
            "kg_co2": round(self.footprint.kg_co2, 4),
            "kg_low": round(self.footprint.kg_low, 4),
            "kg_high": round(self.footprint.kg_high, 4),
        }
        if submit_time is not None:
            d["delay_h"] = round((self.start - floor_hour(submit_time)).total_seconds() / 3600, 1)
        return d


@dataclass(frozen=True)
class Placement:
    job_id: str
    feasible: bool
    chosen: Option | None
    baseline: Option | None
    alternatives: tuple[Option, ...]
    reason: str                      # explanation, or why infeasible
    candidates_considered: int

    def as_dict(self, submit_time: datetime | None = None) -> dict:
        def opt(o):
            return o.as_dict(submit_time) if o else None
        return {
            "job_id": self.job_id,
            "feasible": self.feasible,
            "chosen": opt(self.chosen),
            "baseline": opt(self.baseline),
            "alternatives": [opt(a) for a in self.alternatives],
            "reason": self.reason,
            "candidates_considered": self.candidates_considered,
        }


def floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _pct(new: float, old: float) -> str:
    if old <= 0:
        return "n/a"
    change = 100.0 * (old - new) / old
    return f"{abs(change):.0f}% {'less' if change >= 0 else 'more'}"


def _regions_for(job: Job, surface: Surface) -> tuple[list[str], str | None]:
    regions = list(job.allowed_regions) if job.allowed_regions else list(surface.unit)
    unknown = [r for r in regions if r not in surface.regions]
    if unknown:
        return [], f"unknown region(s): {', '.join(unknown)}"
    if job.data_residency:
        if job.submit_region not in surface.regions:
            return [], f"submit region {job.submit_region} is unknown, so residency cannot be checked"
        geo = surface.regions[job.submit_region].geo
        regions = [r for r in regions if surface.regions[r].geo == geo]
        if not regions:
            return [], f"no allowed region is in {geo} (data residency)"
    if not regions:
        return [], "no allowed regions"
    return regions, None


def schedule(job: Job, surface: Surface, top_k: int = 3) -> Placement:
    """Place one job. Never raises for an infeasible job; returns feasible=False with a reason."""
    def infeasible(reason: str, baseline: Option | None = None, n: int = 0) -> Placement:
        return Placement(job.id, False, None, baseline, (), reason, n)

    if job.gpu_hours <= 0 or job.gpus < 1:
        return infeasible("gpu_hours must be positive and gpus at least 1")
    if job.deadline <= job.submit_time:
        return infeasible("the deadline has already passed")

    start0 = floor_hour(job.submit_time)
    d = job.duration_h
    latest_start = floor_hour(job.deadline - timedelta(hours=d))
    if job.max_delay_h is not None:
        latest_start = min(latest_start, start0 + timedelta(hours=math.floor(job.max_delay_h)))
    if latest_start < start0:
        need = start0 + timedelta(hours=d)
        return infeasible(
            f"the job needs {d} h, so it cannot finish before {hour_key(need)} UTC; "
            f"the deadline is {job.deadline:%Y-%m-%dT%H:%M} UTC"
        )

    regions, problem = _regions_for(job, surface)
    if problem:
        return infeasible(problem)

    it_kwh = job.it_kwh
    baseline_fp = None
    if job.submit_region in surface.regions and surface.covers(job.submit_region, start0, d):
        baseline_fp = surface.window(job.submit_region, start0, d, it_kwh)
    base_region = surface.regions.get(job.submit_region)

    options: list[Option] = []
    t = start0
    while t <= latest_start:
        for rid in regions:
            if not surface.covers(rid, t, d):
                continue
            fp = surface.window(rid, t, d, it_kwh)
            ref = (baseline_fp, base_region) if baseline_fp is not None else None
            c = cost(fp, surface.regions[rid], job.weights, baseline=ref)
            options.append(Option(rid, t, t + timedelta(hours=d), c, fp))
        t += timedelta(hours=1)

    baseline = None
    if baseline_fp is not None:
        baseline = next((o for o in options if o.region == job.submit_region and o.start == start0), None)
        if baseline is None:  # submit region excluded by constraints; still report it
            c = cost(baseline_fp, base_region, job.weights, baseline=(baseline_fp, base_region))
            baseline = Option(job.submit_region, start0, start0 + timedelta(hours=d), c, baseline_fp)

    if not options:
        return infeasible(
            "no forecast covers a feasible window (forecasts reach "
            + ", ".join(f"{r} to {surface.hours(r)[-1] if surface.hours(r) else 'nothing'}" for r in regions)
            + ")",
            baseline,
        )

    order = {rid: i for i, rid in enumerate([job.submit_region] + regions)}
    options.sort(key=lambda o: (round(o.cost, 9), o.start, order.get(o.region, 99)))
    chosen = options[0]
    # Alternatives: the best slot in each *other* region, so the explanation shows
    # what the other places would have cost, not the same region an hour later.
    best_per_region: dict[str, Option] = {}
    for o in options[1:]:
        if o.region != chosen.region and o.region not in best_per_region:
            best_per_region[o.region] = o
    alternatives = tuple(list(best_per_region.values())[:top_k])
    return Placement(job.id, True, chosen, baseline, alternatives,
                     explain(job, chosen, baseline, alternatives), len(options))


def explain(job: Job, chosen: Option, baseline: Option | None, alternatives: tuple[Option, ...]) -> str:
    delay = (chosen.start - floor_hour(job.submit_time)).total_seconds() / 3600
    when = "now" if delay == 0 else f"{delay:.0f} h from now"
    parts = [f"Run in {chosen.region} starting {hour_key(chosen.start)} UTC ({when}), "
             f"finishing {hour_key(chosen.end)} UTC, before the {job.deadline:%Y-%m-%dT%H:%M} UTC deadline."]
    if baseline is not None:
        if chosen.region == baseline.region and chosen.start == baseline.start:
            parts.append("Running now, here, is already the best option.")
        else:
            parts.append(
                f"Compared with running now in {baseline.region}: "
                f"{_pct(chosen.footprint.litres, baseline.footprint.litres)} water "
                f"({chosen.footprint.litres:.2f} vs {baseline.footprint.litres:.2f} L), "
                f"{_pct(chosen.footprint.kg_co2, baseline.footprint.kg_co2)} CO2 "
                f"({chosen.footprint.kg_co2:.3f} vs {baseline.footprint.kg_co2:.3f} kg)."
            )
    else:
        parts.append(f"No forecast for {job.submit_region} now, so there is no run-now comparison.")
    if alternatives:
        alts = "; ".join(f"{a.region} at {hour_key(a.start)} (cost {a.cost:.2f})" for a in alternatives)
        parts.append(f"Next best: {alts}.")
    return " ".join(parts)
