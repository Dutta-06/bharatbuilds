"""Synthetic weather for offline runs (make seed SEED_ARGS=--offline, tests, demos without
internet). Rough October climate per region: a daily sine around a mean. Every row is
labelled weather_source="synthetic" and must never be presented as a forecast."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

# region -> (mean °C, daily half-range °C, RH %, surface pressure hPa, UTC offset h)
OCTOBER = {
    "ap-south-1": (29.5, 3.0, 75, 1009, 5.5),
    "ap-south-2": (26.0, 5.0, 65, 950, 5.5),
    "ap-southeast-1": (28.0, 3.0, 80, 1009, 8),
    "eu-north-1": (8.0, 3.0, 80, 1012, 2),
    "eu-west-1": (11.0, 2.5, 85, 1012, 1),
    "eu-central-1": (11.5, 4.0, 78, 1000, 2),
    "us-east-1": (15.0, 6.0, 65, 1012, -4),
    "us-west-2": (12.5, 8.0, 55, 1000, -7),
}
DEFAULT = (20.0, 5.0, 60, 1010, 0)


def weather(region_id: str, start_utc: datetime, hours: int) -> list[tuple[str, float, float, float]]:
    mean, half, rh, p, offset = OCTOBER.get(region_id, DEFAULT)
    out = []
    for i in range(hours):
        t = start_utc + timedelta(hours=i)
        local = (t.hour + offset) % 24
        phase = math.cos((local - 15) / 24 * 2 * math.pi)  # warmest 3 PM local
        out.append((t.strftime("%Y-%m-%dT%H:00"), round(mean + half * phase, 1),
                    round(min(98, rh - 12 * phase), 0), float(p)))
    return out
