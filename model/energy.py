"""Energy a job will use, before it runs (replaced by measured kWh after)."""

from __future__ import annotations

from . import coefficients as c


def gpu_tdp_w(gpu: str) -> float:
    gpus = c.load()["gpus"]["values"]
    try:
        return float(gpus[gpu.lower()])
    except KeyError:
        raise ValueError(f"unknown GPU {gpu!r}; known: {', '.join(gpus)}") from None


def job_it_kwh(gpu_hours: float, gpu: str = "a100") -> float:
    """IT energy (kWh) for gpu_hours on a GPU type: TDP × utilisation × server overhead."""
    if gpu_hours <= 0:
        raise ValueError("gpu_hours must be positive")
    return (
        gpu_hours
        * gpu_tdp_w(gpu) / 1000.0
        * c.value("job_energy", "gpu_utilisation")
        * c.value("job_energy", "server_overhead")
    )
