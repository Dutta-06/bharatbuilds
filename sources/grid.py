"""48-hour grid outlook for a region: Electricity Maps forecast when available,
else latest value held flat (labelled), else the modelled profile (labelled)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from .carbon import CarbonSourceError, ElectricityMaps, GridHour, ModelledProfile, for_region


def outlook(region, start_utc: datetime, hours: int = 48) -> list[GridHour]:
    keys = [(start_utc + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(hours)]
    src = for_region(region)
    if isinstance(src, ModelledProfile):
        return src.hours(start_utc, hours)

    zone = region.electricity_maps_zone
    latest = src.latest(zone)
    mix = latest.mix or region.grid_mix
    try:
        fc = {g.hour: g for g in src.forecast(zone)}
    except CarbonSourceError:
        fc = {}
    out = []
    for k in keys:
        if k in fc:
            out.append(replace(fc[k], mix=mix))
        else:
            out.append(GridHour(k, latest.ci_g_per_kwh, mix, "electricitymaps-latest-held"))
    return out


__all__ = ["outlook", "ElectricityMaps", "ModelledProfile", "GridHour"]
