import csv
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import pull_history  # noqa: E402
import sample_trace  # noqa: E402
from validate_data import validate_history  # noqa: E402

from model import regions  # noqa: E402
from scheduler.trace import load  # noqa: E402
from sources import openmeteo  # noqa: E402


def test_synthetic_trace_shape():
    rows = sample_trace.synthetic(200, random.Random(1), ["ap-south-1", "eu-north-1"])
    assert len(rows) == 200
    assert all(r["source"] == "synthetic" for r in rows)
    assert all(0.25 <= r["gpu_hours"] <= 200 for r in rows)
    assert all(r["slack_h"] >= r["gpu_hours"] / r["gpus"] for r in rows)
    assert [r["submit_offset_h"] for r in rows] == sorted(r["submit_offset_h"] for r in rows)


def test_alibaba_parser(tmp_path):
    path = tmp_path / "pai_task_table.csv"
    lines = [
        "j1,worker,2,Terminated,1000,8200,600,29,100,V100",    # 2 inst × 1 GPU × 2 h = 4 GPU-h
        "j2,worker,1,Failed,0,3600,600,29,100,V100",            # failed: dropped
        "j3,ps,1,Terminated,0,3600,600,29,,",                   # no GPU: dropped
        "j4,worker,1,Terminated,5000,5100,600,29,50,T4",        # too short: dropped
        "j5,worker,1,Terminated,2000,9200,600,29,50,T4",        # 0.5 GPU × 2 h = 1 GPU-h
    ]
    path.write_text("\n".join(lines) + "\n")
    rows = sample_trace.from_alibaba(path, 10, random.Random(0), ["ap-south-1"])
    assert [r["gpu_hours"] for r in rows] == [4.0, 1.0]
    assert rows[0]["gpus"] == 2 and rows[1]["gpus"] == 1
    assert rows[0]["submit_offset_h"] == 0.0
    assert all(r["source"] == "alibaba-gpu-v2020" for r in rows)


def test_shipped_synthetic_trace_loads_as_jobs():
    jobs = load(ROOT / "data" / "trace.synthetic.csv", datetime(2026, 10, 5))
    assert len(jobs) == 500
    known = set(regions.load())
    assert all(j.submit_region in known and j.deadline > j.submit_time for j in jobs)


def test_pull_history_rows_and_validation(tmp_path, monkeypatch):
    monkeypatch.delenv("ELECTRICITYMAPS_TOKEN", raising=False)
    hours = [f"2026-09-{d:02d}T{h:02d}:00" for d in range(1, 31) for h in range(24)]
    monkeypatch.setattr(openmeteo, "recent",
                        lambda lat, lon, days: [(t, 30.0, 60.0, 1005.0) for t in hours])
    region = regions.get("ap-south-1")
    rows = pull_history.rows_for(region, 30, datetime(2026, 10, 1))
    assert len(rows) == 720 and rows[0]["ci_source"] == "modelled"
    assert 20 < rows[0]["t_wb"] < 30

    monkeypatch.setattr(pull_history, "OUT", tmp_path / "data" / "history")
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "regions.yaml").write_text((ROOT / "data" / "regions.yaml").read_text())
    pull_history.write("ap-south-1", rows)
    with (tmp_path / "data" / "history" / "ap-south-1.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 720
    errors = validate_history(tmp_path, min_days=30)
    assert not any("ap-south-1" in e for e in errors)
    assert any("eu-north-1" in e for e in errors)  # not pulled
