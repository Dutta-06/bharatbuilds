"""Splittable jobs (Step 11): run a job in up to K contiguous chunks across hours and regions.

For checkpointable work (training with checkpoints, evaluation sweeps), the job's
`duration_h` hours need not be consecutive or in one region. Model:

    x[r, t] in {0, 1}         run in region r during hour t (at the job's full GPU width)
    sum_r x[r, t] <= 1        one place at a time
    sum_{r,t} x[r, t] = D     all the work gets done, within [submit hour, deadline)
    s[r, t] >= x[r, t] - x[r, t-1]   a chunk starts
    sum s <= K                at most K chunks (each restart costs a checkpoint reload)
    minimise sum c[r, t] * x[r, t]

c[r, t] is the normalised cost of that hour (same weights and baseline as the greedy
scheduler; linear because footprints add over hours).

Two exact solvers: OR-Tools CP-SAT (`solve_cpsat`, used where OR-Tools is installed)
and a dynamic programme in plain Python (`solve_dp`, used in Lambda; no dependency).
Tests check they agree. Moving checkpoints between regions has a data-transfer cost we
do not model; that is a stated limitation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from model.cost import cost

from .greedy import Job, floor_hour
from .surface import Surface, hour_key, sum_footprints

SCALE = 1_000_000  # CP-SAT needs integer costs


@dataclass(frozen=True)
class Chunk:
    region: str
    start: datetime
    hours: int

    @property
    def end(self) -> datetime:
        return self.start + timedelta(hours=self.hours)


def _grid(job: Job, surface: Surface):
    """Hours in the window, candidate regions, and per-hour costs (None where no forecast)."""
    start = floor_hour(job.submit_time)
    end = floor_hour(job.deadline)  # last hour must *finish* by the deadline
    hours = []
    t = start
    while t + timedelta(hours=1) <= job.deadline and t < end + timedelta(hours=1):
        hours.append(t)
        t += timedelta(hours=1)
    regions = list(job.allowed_regions or surface.unit)
    if job.data_residency:
        geo = surface.regions[job.submit_region].geo
        regions = [r for r in regions if surface.regions[r].geo == geo]
    per_hour_kwh = job.it_kwh / job.duration_h
    base = None
    if surface.covers(job.submit_region, start, job.duration_h):
        base = (surface.window(job.submit_region, start, job.duration_h, job.it_kwh), surface.regions[job.submit_region])
    costs = {}
    for r in regions:
        for i, h in enumerate(hours):
            fp = surface.unit.get(r, {}).get(hour_key(h))
            if fp is None:
                continue
            one = sum_footprints([fp], per_hour_kwh, hour_key(h))
            costs[(r, i)] = cost(one, surface.regions[r], job.weights, baseline=base)
    return hours, regions, costs, base


def solve_dp(job: Job, surface: Surface, max_chunks: int) -> list[Chunk] | None:
    hours, regions, costs, _ = _grid(job, surface)
    D, T = job.duration_h, len(hours)
    IDLE = -1
    # state: (hours_done, chunks_used, last) -> (cost, path)
    states = {(0, 0, IDLE): (0.0, ())}
    for i in range(T):
        nxt: dict = {}
        remaining_after = T - i - 1
        for (done, used, last), (c, path) in states.items():
            options = [(IDLE, 0.0)] + [(k, costs[(r, i)]) for k, r in enumerate(regions) if (r, i) in costs]
            for choice, add in options:
                d2 = done + (choice != IDLE)
                u2 = used + (choice != IDLE and choice != last)
                if d2 > D or u2 > max_chunks or D - d2 > remaining_after:
                    continue
                key = (d2, u2, choice)
                val = (c + add, path + (choice,))
                if key not in nxt or val[0] < nxt[key][0] - 1e-12:
                    nxt[key] = val
        states = nxt
    finals = [v for (done, _, _), v in states.items() if done == D]
    if not finals:
        return None
    _, path = min(finals, key=lambda v: v[0])
    return _chunks(path, hours, regions)


def solve_cpsat(job: Job, surface: Surface, max_chunks: int, time_limit_s: float = 10.0) -> list[Chunk] | None:
    from ortools.sat.python import cp_model

    hours, regions, costs, _ = _grid(job, surface)
    m = cp_model.CpModel()
    x = {k: m.NewBoolVar(f"x_{k[0]}_{k[1]}") for k in costs}
    for i in range(len(hours)):
        m.Add(sum(x[(r, i)] for r in regions if (r, i) in x) <= 1)
    m.Add(sum(x.values()) == job.duration_h)
    starts = []
    for (r, i), var in x.items():
        s = m.NewBoolVar(f"s_{r}_{i}")
        prev = x.get((r, i - 1))
        m.Add(s >= var - prev) if prev is not None else m.Add(s >= var)
        starts.append(s)
    m.Add(sum(starts) <= max_chunks)
    m.Minimize(sum(int(round(costs[k] * SCALE)) * v for k, v in x.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 4
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    path = []
    for i in range(len(hours)):
        chosen = [k for k, r in enumerate(regions) if (r, i) in x and solver.Value(x[(r, i)])]
        path.append(chosen[0] if chosen else -1)
    return _chunks(path, hours, regions)


def _chunks(path, hours, regions) -> list[Chunk]:
    chunks: list[Chunk] = []
    for i, choice in enumerate(path):
        if choice == -1:
            continue
        r = regions[choice]
        if chunks and chunks[-1].region == r and chunks[-1].end == hours[i]:
            chunks[-1] = Chunk(r, chunks[-1].start, chunks[-1].hours + 1)
        else:
            chunks.append(Chunk(r, hours[i], 1))
    return chunks


def plan_cost(job: Job, surface: Surface, chunks: list[Chunk]) -> float:
    _, regions, costs, _ = _grid(job, surface)
    start = floor_hour(job.submit_time)
    total = 0.0
    for c in chunks:
        for h in range(c.hours):
            i = int((c.start - start).total_seconds() // 3600) + h
            total += costs[(c.region, i)]
    return total


def split(job: Job, surface: Surface, max_chunks: int = 2, solver: str = "auto") -> dict:
    """Best plan with at most max_chunks chunks, as a JSON-ready dict with per-chunk footprints."""
    if max_chunks < 1:
        raise ValueError("max_chunks must be at least 1")
    use_cpsat = solver == "cpsat"
    if solver == "auto":
        try:
            import ortools  # noqa: F401
            use_cpsat = True
        except ImportError:
            use_cpsat = False
    chunks = solve_cpsat(job, surface, max_chunks) if use_cpsat else solve_dp(job, surface, max_chunks)
    if not chunks:
        return {"feasible": False, "reason": "no combination of hours and regions fits before the deadline"}
    per_hour = job.it_kwh / job.duration_h
    parts = []
    for c in chunks:
        fp = surface.window(c.region, c.start, c.hours, per_hour * c.hours)
        parts.append({"region": c.region, "start": hour_key(c.start), "end": hour_key(c.end), "hours": c.hours,
                      "litres": round(fp.litres, 3), "kg_co2": round(fp.kg_co2, 4)})
    return {"feasible": True, "solver": "or-tools cp-sat" if use_cpsat else "exact dp",
            "chunks": parts, "cost": round(plan_cost(job, surface, chunks), 4),
            "litres": round(sum(p["litres"] for p in parts), 3),
            "kg_co2": round(sum(p["kg_co2"] for p in parts), 4)}
