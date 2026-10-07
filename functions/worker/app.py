"""worker: the workload that actually runs in the chosen region.

A small, dependency-free training loop (logistic regression by gradient descent
on synthetic data) that keeps one vCPU busy for `seconds`. It stands in for the
user's GPU job: Lambda has no GPUs. It reports what it can really measure:
wall time and CPU time on the machine it ran on, and the AWS region.

Event:  {"job_id": "...", "seconds": 20}
Return: {"region", "wall_s", "cpu_s", "epochs", "final_loss", "started_at", "finished_at"}
"""

import math
import os
import random
import resource
import time
from datetime import datetime, timezone


def train(seconds: float, seed: int = 0) -> tuple[int, float]:
    rng = random.Random(seed)
    w_true = [rng.uniform(-1, 1) for _ in range(16)]
    data = []
    for _ in range(2000):
        x = [rng.uniform(-1, 1) for _ in range(16)]
        y = 1.0 if sum(a * b for a, b in zip(w_true, x)) > 0 else 0.0
        data.append((x, y))
    w = [0.0] * 16
    epochs, loss, deadline = 0, 0.0, time.monotonic() + seconds
    while time.monotonic() < deadline:
        grad, loss = [0.0] * 16, 0.0
        for x, y in data:
            z = sum(a * b for a, b in zip(w, x))
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
            loss -= y * math.log(p + 1e-12) + (1 - y) * math.log(1 - p + 1e-12)
            for i in range(16):
                grad[i] += (p - y) * x[i]
        w = [wi - 0.5 * g / len(data) for wi, g in zip(w, grad)]
        loss /= len(data)
        epochs += 1
    return epochs, loss


def handler(event, context):
    seconds = max(1.0, min(600.0, float(event.get("seconds", 20))))
    started = datetime.now(timezone.utc)
    cpu0, wall0 = resource.getrusage(resource.RUSAGE_SELF).ru_utime, time.monotonic()
    epochs, loss = train(seconds, seed=hash(event.get("job_id", "")) & 0xFFFF)
    cpu_s = resource.getrusage(resource.RUSAGE_SELF).ru_utime - cpu0
    return {
        "job_id": event.get("job_id"),
        "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        "wall_s": round(time.monotonic() - wall0, 3),
        "cpu_s": round(cpu_s, 3),
        "epochs": epochs,
        "final_loss": round(loss, 5),
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
