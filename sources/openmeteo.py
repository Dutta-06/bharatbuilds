"""Weather for one hour at one point from Open-Meteo (stdlib only)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
VARS = ("temperature_2m", "relative_humidity_2m", "surface_pressure")


def _get(url: str, params: dict, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": "pravaah/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def parse_hour(text: str) -> datetime:
    """ISO hour, UTC. A trailing Z or offset is honoured; naive means UTC."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(minute=0, second=0, microsecond=0)


def hour_weather(lat: float, lon: float, hour_utc: datetime) -> tuple[float, float, float]:
    """(temperature °C, RH %, surface pressure hPa) for one UTC hour (forecast or recent past)."""
    stamp = hour_utc.strftime("%Y-%m-%dT%H:00")
    raw = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "hourly": ",".join(VARS),
        "timezone": "UTC", "start_hour": stamp, "end_hour": stamp,
    })
    h = raw["hourly"]
    return h["temperature_2m"][0], h["relative_humidity_2m"][0], h["surface_pressure"][0]


def history(lat: float, lon: float, start: datetime, end: datetime) -> list[tuple[str, float, float, float]]:
    """Hourly (time, T, RH, P) from the archive API between two UTC dates inclusive."""
    raw = _get(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon, "hourly": ",".join(VARS), "timezone": "UTC",
        "start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d"),
    }, timeout=60.0)
    h = raw["hourly"]
    return [
        (t, temp, rh, p)
        for t, temp, rh, p in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"], h["surface_pressure"])
        if None not in (temp, rh, p)
    ]


def last_full_year(today: datetime | None = None) -> tuple[datetime, datetime]:
    today = today or datetime.now(timezone.utc).replace(tzinfo=None)
    end = today - timedelta(days=7)  # archive lags about 5 days
    return end - timedelta(days=364), end


def forecast(lat: float, lon: float, hours: int = 48) -> list[tuple[str, float, float, float]]:
    """Next `hours` hourly (UTC time, T, RH, P), starting at the current UTC hour."""
    raw = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "hourly": ",".join(VARS), "timezone": "UTC",
        "forecast_days": max(2, (hours + 47) // 24),
    })
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    h = raw["hourly"]
    rows = [
        (t, temp, rh, p)
        for t, temp, rh, p in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"], h["surface_pressure"])
        if t >= now and None not in (temp, rh, p)
    ]
    return rows[:hours]


def recent(lat: float, lon: float, days: int) -> list[tuple[str, float, float, float]]:
    """Hourly (UTC time, T, RH, P) for the last `days` days up to the current hour.

    Uses the forecast endpoint's past_days (max 92), which has no archive lag, so it
    overlaps with the last-24 h carbon history the Electricity Maps free tier gives.
    """
    if not 1 <= days <= 92:
        raise ValueError("days must be 1-92 (Open-Meteo past_days limit); use history() for older data")
    raw = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "hourly": ",".join(VARS), "timezone": "UTC",
        "past_days": days, "forecast_days": 1,
    }, timeout=60.0)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    h = raw["hourly"]
    return [
        (t, temp, rh, p)
        for t, temp, rh, p in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"], h["surface_pressure"])
        if t <= now and None not in (temp, rh, p)
    ]
