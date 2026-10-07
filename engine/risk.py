"""Combine the hazard models into 48-hour strips for one point."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from . import thresholds
from .heat_index import heat_index
from .openmeteo import Forecast, HourlyWeather
from .waterlogging import DRAINAGE_LAG_HOURS, WINDOW_HOURS, waterlogging_levels
from .wbgt import wbgt_outdoor
from .windows import summarize

STRIP_HOURS = 48


def assess_heat_hour(hour: HourlyWeather, work: str, acclimatised: bool = True) -> dict:
    """WBGT when solar and wind are present, otherwise heat index."""
    if hour.solar is not None and hour.wind is not None:
        value = wbgt_outdoor(hour.temperature, hour.humidity, hour.solar, hour.wind)
        level = thresholds.wbgt_level(value, work, acclimatised)
        metric = "wbgt"
    else:
        value = heat_index(hour.temperature, hour.humidity)
        level = thresholds.heat_index_level(value, work)
        metric = "heat_index"
    return {
        "time": hour.time.isoformat(timespec="minutes"),
        "level": level,
        "metric": metric,
        "value": round(value, 1),
    }


def heat_strip(hours: Sequence[HourlyWeather], work: str, acclimatised: bool = True) -> list[dict]:
    return [assess_heat_hour(h, work, acclimatised) for h in hours]


def waterlogging_strip(
    hours: Sequence[HourlyWeather],
    has_hotspot: bool = False,
    elevation_m: float | None = None,
    city_ref_elevation_m: float | None = None,
    lead_in: Sequence[HourlyWeather] = (),
) -> list[dict]:
    levels = waterlogging_levels(
        [h.precipitation for h in hours],
        has_hotspot=has_hotspot,
        elevation_m=elevation_m,
        city_ref_elevation_m=city_ref_elevation_m,
        lead_in=[h.precipitation for h in lead_in],
    )
    return [
        {
            "time": h.time.isoformat(timespec="minutes"),
            "level": level,
            "metric": "rain_mm",
            "value": round(h.precipitation, 1),
        }
        for h, level in zip(hours, levels)
    ]


def window_from(forecast: Forecast, now: datetime | None = None) -> tuple[list, list]:
    """(lead_in hours, the next STRIP_HOURS hours starting at the current hour)."""
    now = (now or forecast.local_now()).replace(minute=0, second=0, microsecond=0)
    idx = next((i for i, h in enumerate(forecast.hours) if h.time >= now), None)
    if idx is None:
        raise ValueError(f"forecast has no hours at or after {now.isoformat()}")
    lead_in = forecast.hours[max(0, idx - (WINDOW_HOURS - 1) - DRAINAGE_LAG_HOURS) : idx]
    return lead_in, forecast.hours[idx : idx + STRIP_HOURS]


def assess(
    forecast: Forecast,
    work: str = "heavy",
    lang: str = "en",
    has_hotspot: bool = False,
    city_ref_elevation_m: float | None = None,
    acclimatised: bool = True,
    now: datetime | None = None,
    elevation_m: float | None = None,
) -> dict:
    """Both hazards for one point, with strips and plain-language windows.

    ``elevation_m`` is the cell's elevation; it defaults to the forecast's.
    """
    lead_in, hours = window_from(forecast, now)
    times = [h.time for h in hours]
    result = {"work": work, "lang": lang, "hazards": {}}
    for hazard, strip in (
        ("heat", heat_strip(hours, work, acclimatised)),
        (
            "waterlogging",
            waterlogging_strip(
                hours,
                has_hotspot=has_hotspot,
                elevation_m=forecast.elevation if elevation_m is None else elevation_m,
                city_ref_elevation_m=city_ref_elevation_m,
                lead_in=lead_in,
            ),
        ),
    ):
        levels = [s["level"] for s in strip]
        result["hazards"][hazard] = {
            "strip": strip,
            **summarize(levels, times, work=work, hazard=hazard, lang=lang),
        }
    return result
