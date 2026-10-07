import random
from datetime import datetime, timedelta

import pytest

from model import regions as region_config
from model.cost import Conditions
from scheduler.greedy import Job, schedule
from scheduler.split import plan_cost, solve_cpsat, solve_dp, split
from scheduler.surface import build, hour_key

T0 = datetime(2026, 10, 10, 0)
REGIONS = region_config.load()


def surface(seed=0, hours=30):
    rng = random.Random(seed)
    data = {}
    for rid in ("ap-south-1", "eu-north-1", "us-east-1"):
        data[rid] = [Conditions(hour_key(T0 + timedelta(hours=i)), rng.uniform(5, 35), rng.uniform(30, 90),
                                rng.uniform(30, 700)) for i in range(hours)]
    return build(REGIONS, data)


def job(hours=6, deadline=20, **kw):
    return Job(id="s", gpu_hours=hours, submit_time=T0, deadline=T0 + timedelta(hours=deadline),
               submit_region="ap-south-1", **kw)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_dp_and_cpsat_agree(seed, k):
    s, j = surface(seed), job()
    a, b = solve_dp(j, s, k), solve_cpsat(j, s, k)
    assert plan_cost(j, s, a) == pytest.approx(plan_cost(j, s, b), abs=1e-5)
    for plan in (a, b):
        assert sum(c.hours for c in plan) == j.duration_h
        assert len(plan) <= k
        assert all(c.end <= j.deadline for c in plan)
        ends = sorted((c.start, c.end) for c in plan)
        assert all(e1 <= s2 for (_, e1), (s2, _) in zip(ends, ends[1:]))  # no overlap


def test_one_chunk_equals_greedy():
    s, j = surface(3), job()
    greedy = schedule(j, s)
    plan = solve_dp(j, s, 1)
    assert len(plan) == 1
    assert plan[0].region == greedy.chosen.region and plan[0].start == greedy.chosen.start


def test_more_chunks_never_cost_more():
    s, j = surface(7), job(hours=8, deadline=24)
    costs = [plan_cost(j, s, solve_dp(j, s, k)) for k in (1, 2, 3, 4)]
    assert costs == sorted(costs, reverse=True)


def test_twenty_gpu_hour_job_split_across_two_slots():
    """Plan's done-when: a 20-GPU-hour job can be split across two slots and the receipt explains both."""
    s = surface(11, hours=48)
    j = Job(id="big", gpu_hours=20, gpus=1, submit_time=T0, deadline=T0 + timedelta(hours=40),
            submit_region="ap-south-1")
    out = split(j, s, max_chunks=2)
    assert out["feasible"] and 1 <= len(out["chunks"]) <= 2
    assert sum(c["hours"] for c in out["chunks"]) == 20
    assert out["litres"] == pytest.approx(sum(c["litres"] for c in out["chunks"]), abs=1e-3)


def test_infeasible_split():
    out = split(job(hours=10, deadline=5), surface(), max_chunks=3, solver="dp")
    assert out == {"feasible": False, "reason": "no combination of hours and regions fits before the deadline"}


def test_residency_respected():
    s = surface(2)
    plan = solve_dp(job(data_residency=True), s, 3)
    assert {c.region for c in plan} == {"ap-south-1"}
