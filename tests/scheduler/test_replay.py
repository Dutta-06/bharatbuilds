from datetime import datetime, timedelta

from model import regions as region_config
from model.cost import Conditions, Weights
from scheduler.greedy import Job
from scheduler.replay import replay, stay_home, with_slack, with_weights
from scheduler.surface import build, hour_key

T0 = datetime(2026, 10, 5)
REGIONS = region_config.load()


def surface():
    hot = [Conditions(hour_key(T0 + timedelta(hours=i)), 33 if (i % 24) < 12 else 26, 70, 700 if (i % 24) < 12 else 500)
           for i in range(72)]
    cool = [Conditions(hour_key(T0 + timedelta(hours=i)), 9, 80, 30) for i in range(72)]
    return build(REGIONS, {"ap-south-1": hot, "eu-north-1": cool})


def jobs():
    return [Job(id=f"j{i}", gpu_hours=2, submit_time=T0 + timedelta(hours=i), deadline=T0 + timedelta(hours=i + 14),
                submit_region="ap-south-1") for i in range(0, 24, 3)]


def test_replay_saves_and_meets_deadlines():
    r = replay(jobs(), surface())
    assert r["jobs"] == 8
    assert r["saved_pct"]["litres"] > 0 and r["saved_pct"]["kg_co2"] > 0
    assert r["deadline_hit_rate_pct"] == 100.0
    assert r["moved_region_pct"] > 0


def test_time_only_keeps_region_and_saves_less():
    s = surface()
    both = replay(jobs(), s)
    home = replay(stay_home(jobs()), s)
    assert home["moved_region_pct"] == 0
    assert 0 < home["saved_pct"]["kg_co2"] < both["saved_pct"]["kg_co2"]


def test_zero_slack_means_no_waiting():
    r = replay(stay_home(with_slack(jobs(), 0)), surface())
    assert r["median_delay_h"] == 0 and r["saved_pct"]["litres"] == 0


def test_weights_scenarios_run():
    r = replay(with_weights(jobs(), Weights(0, 1)), surface())
    assert r["jobs"] == 8
