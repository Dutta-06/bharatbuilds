"""Load a trace CSV (scripts/sample_trace.py) as scheduler Jobs."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from model.cost import Weights

from .greedy import Job


def load(path: Path, week_start: datetime, weights: Weights = Weights()) -> list[Job]:
    jobs = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            submit = week_start + timedelta(hours=float(row["submit_offset_h"]))
            jobs.append(Job(
                id=row["job_id"],
                gpu_hours=float(row["gpu_hours"]),
                gpus=int(row["gpus"]),
                submit_time=submit,
                deadline=submit + timedelta(hours=float(row["slack_h"])),
                submit_region=row["submit_region"],
                weights=weights,
            ))
    return jobs
