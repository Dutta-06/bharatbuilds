"""Feature rows for the two models. Same code at training and serving time."""

from __future__ import annotations

import math
from datetime import datetime

WETBULB_FEATURES = ["provider_t_wb", "provider_t_db", "provider_rh", "lead_h", "hour_sin", "hour_cos",
                    "doy_sin", "doy_cos", "recent_residual"]
CARBON_FEATURES = ["last_ci", "lead_h", "hour_sin", "hour_cos", "dow", "same_hour_yesterday"]


def _time(hour: str) -> dict:
    dt = datetime.strptime(hour[:13], "%Y-%m-%dT%H")
    h = 2 * math.pi * dt.hour / 24
    d = 2 * math.pi * dt.timetuple().tm_yday / 365.25
    return {"hour_sin": math.sin(h), "hour_cos": math.cos(h), "doy_sin": math.sin(d), "doy_cos": math.cos(d),
            "dow": dt.weekday()}


def wetbulb_row(hour: str, lead_h: float, provider_t_wb: float, provider_t_db: float, provider_rh: float,
                recent_residual: float) -> dict:
    """recent_residual: observed minus provider wet-bulb at issue time (0 if unknown)."""
    return {"provider_t_wb": provider_t_wb, "provider_t_db": provider_t_db, "provider_rh": provider_rh,
            "lead_h": lead_h, "recent_residual": recent_residual, **_time(hour)}


def carbon_row(hour: str, lead_h: float, last_ci: float, same_hour_yesterday: float | None) -> dict:
    return {"last_ci": last_ci, "lead_h": lead_h,
            "same_hour_yesterday": last_ci if same_hour_yesterday is None else same_hour_yesterday, **_time(hour)}
