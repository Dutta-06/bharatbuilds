from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from model import regions as region_config
from model.cost import Conditions, Weights
from scheduler.greedy import Job, schedule
from scheduler.surface import build, hour_key

T0 = datetime(2026, 10, 10, 6, 0)  # UTC
REGIONS = region_config.load()


def conds(hours, t_db, rh, ci, start=T0):
    """Conditions for consecutive hours; t_db/rh/ci may be constants or callables of hour index."""
    val = lambda v, i: v(i) if callable(v) else v  # noqa: E731
    return [Conditions(hour_key(start + timedelta(hours=i)), val(t_db, i), val(rh, i), val(ci, i))
            for i in range(hours)]


@pytest.fixture
def surface():
    # Mumbai: hot, humid, coal. Stockholm: cool, clean.
    # Singapore: hot/humid, gas. Mumbai gets cooler and cleaner from hour 10 (night).
    return build(REGIONS, {
        "ap-south-1": conds(48, lambda i: 33 if i < 10 else 26, 70, lambda i: 700 if i < 10 else 550),
        "eu-north-1": conds(48, 10, 80, 30),
        "ap-southeast-1": conds(48, 31, 80, 480),
    })


def job(**kw):
    base = dict(id="j1", gpu_hours=4, submit_time=T0 + timedelta(minutes=20),
                deadline=T0 + timedelta(hours=24), submit_region="ap-south-1")
    base.update(kw)
    return Job(**base)


def test_picks_cleanest_coolest_slot(surface):
    p = schedule(job(), surface)
    assert p.feasible
    assert p.chosen.region == "eu-north-1"
    assert p.chosen.cost < 1.0
    assert p.baseline.region == "ap-south-1" and p.baseline.start == T0
    assert p.baseline.cost == pytest.approx(1.0)
    assert len(p.alternatives) == 2  # one per other region
    assert len({a.region for a in p.alternatives} | {p.chosen.region}) == 3
    assert "eu-north-1" in p.reason and "less water" in p.reason and "Next best" in p.reason


def test_residency_keeps_job_in_geo_and_waits_for_night(surface):
    p = schedule(job(data_residency=True), surface)
    assert p.chosen.region == "ap-south-1"
    assert p.chosen.start >= T0 + timedelta(hours=10)  # waits for the cooler, cleaner night
    assert p.chosen.end <= T0 + timedelta(hours=24)


def test_allowed_regions(surface):
    p = schedule(job(allowed_regions=("ap-southeast-1", "ap-south-1")), surface)
    assert p.chosen.region in {"ap-southeast-1", "ap-south-1"}


def test_max_delay_limits_waiting(surface):
    p = schedule(job(allowed_regions=("ap-south-1",), max_delay_h=2), surface)
    assert p.chosen.start <= T0 + timedelta(hours=2)


def test_multi_gpu_job_shortens_window(surface):
    j = job(gpu_hours=8, gpus=4)
    assert j.duration_h == 2
    p = schedule(j, surface)
    assert p.chosen.end - p.chosen.start == timedelta(hours=2)


def test_window_sums_energy_over_hours(surface):
    j = job(gpu_hours=3)
    p = schedule(j, surface)
    assert p.chosen.footprint.it_kwh == pytest.approx(j.it_kwh)
    assert p.chosen.footprint.litres_low <= p.chosen.footprint.litres <= p.chosen.footprint.litres_high


def test_deadline_now_runs_now_or_fails(surface):
    # deadline exactly fits: only the current hour works
    p = schedule(job(gpu_hours=1, deadline=T0 + timedelta(hours=1)), surface)
    assert p.feasible and p.chosen.start == T0
    # too soon to finish
    p = schedule(job(gpu_hours=4, deadline=T0 + timedelta(hours=2)), surface)
    assert not p.feasible
    assert "cannot finish" in p.reason


def test_deadline_in_past(surface):
    p = schedule(job(deadline=T0 - timedelta(hours=1)), surface)
    assert not p.feasible and "passed" in p.reason


def test_no_forecast_coverage(surface):
    p = schedule(job(submit_time=T0 + timedelta(hours=60), deadline=T0 + timedelta(hours=80)), surface)
    assert not p.feasible and "no forecast covers" in p.reason


def test_unknown_or_empty_regions(surface):
    assert "unknown region" in schedule(job(allowed_regions=("mars-1",)), surface).reason
    p = schedule(job(data_residency=True, allowed_regions=("eu-north-1",)), surface)
    assert not p.feasible and "data residency" in p.reason


def test_weights_can_flip_the_choice():
    # Same weather everywhere; Singapore grid is gas (low water, high carbon),
    # Stockholm placeholder mix has nuclear/biomass (more grid water, very low carbon).
    surface = build(REGIONS, {
        "ap-southeast-1": conds(6, 10, 60, 480),
        "eu-north-1": conds(6, 10, 60, 30),
    })
    water = schedule(job(submit_region="ap-southeast-1", deadline=T0 + timedelta(hours=6),
                         weights=Weights(1, 0)), surface)
    carbon = schedule(job(submit_region="ap-southeast-1", deadline=T0 + timedelta(hours=6),
                          weights=Weights(0, 1)), surface)
    assert water.chosen.region == "ap-southeast-1"
    assert carbon.chosen.region == "eu-north-1"


def test_running_now_is_best_says_so():
    surface = build(REGIONS, {"eu-north-1": conds(6, 10, 60, 30)})
    p = schedule(job(submit_region="eu-north-1", deadline=T0 + timedelta(hours=6)), surface)
    assert p.chosen.start == T0 and "already the best" in p.reason


def test_as_dict_is_json_ready(surface):
    import json
    p = schedule(job(), surface)
    d = p.as_dict(submit_time=job().submit_time)
    json.dumps(d)
    assert d["chosen"]["delay_h"] >= 0 and d["baseline"]["delay_h"] == 0


def test_every_trace_like_job_gets_slot_or_reason(surface):
    """Plan's done-when: every job gets a feasible slot or a clear infeasibility reason."""
    jobs = [job(id=f"j{i}", gpu_hours=g, gpus=n, deadline=T0 + timedelta(hours=h))
            for i, (g, n, h) in enumerate([(1, 1, 1), (4, 1, 3), (8, 2, 30), (100, 8, 20), (50, 1, 100)])]
    for j in jobs:
        p = schedule(j, surface)
        assert p.feasible or p.reason, j
        if p.feasible:
            assert p.chosen.end <= j.deadline


def test_prefix_window_matches_direct_sum(surface):
    from scheduler.surface import sum_footprints
    start = T0 + timedelta(hours=7)
    fast = surface.window("ap-south-1", start, 5, 2.0)
    direct = sum_footprints([surface.unit["ap-south-1"][hour_key(start + timedelta(hours=i))] for i in range(5)],
                            2.0 / 5, hour_key(start))
    for name in ("litres", "kg_co2", "litres_low", "kg_high", "t_wb", "it_kwh"):
        assert getattr(fast, name) == pytest.approx(getattr(direct, name)), name
