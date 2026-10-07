"""Minimal Open-Meteo client (stdlib only, so it runs in a bare Lambda)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = (
    "temperature_2m",
    "relative_humidity_2m",
    "shortwave_radiation",
    "wind_speed_10m",
    "precipitation",
)


@dataclass(frozen=True)
class HourlyWeather:
    time: datetime  # local time, naive
    temperature: float  # °C
    humidity: float  # %
    solar: float | None  # W/m2, global horizontal
    wind: float | None  # m/s at 10 m
    precipitation: float  # mm in the hour ending at `time`


@dataclass(frozen=True)
class Forecast:
    latitude: float
    longitude: float
    elevation: float | None
    utc_offset_seconds: int
    hours: list[HourlyWeather]

    def local_now(self) -> datetime:
        tz = timezone(timedelta(seconds=self.utc_offset_seconds))
        return datetime.now(tz).replace(tzinfo=None)


def forecast_url(lat: float, lon: float, past_hours: int = 6) -> str:
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "past_hours": past_hours,
        "forecast_days": 3,
    }
    return f"{FORECAST_URL}?{urllib.parse.urlencode(params)}"


def fetch_raw(lat: float, lon: float, timeout: float = 10.0) -> dict:
    """GET the raw Open-Meteo JSON for one point."""
    req = urllib.request.Request(forecast_url(lat, lon), headers={"User-Agent": "chhaanv/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def parse(raw: dict) -> Forecast:
    """Turn an Open-Meteo response into a ``Forecast``. Missing values become None."""
    h = raw["hourly"]
    n = len(h["time"])

    def col(name: str) -> list:
        return h.get(name) or [None] * n

    hours = []
    for t, temp, rh, sw, wind, rain in zip(
        h["time"],
        col("temperature_2m"),
        col("relative_humidity_2m"),
        col("shortwave_radiation"),
        col("wind_speed_10m"),
        col("precipitation"),
    ):
        if temp is None or rh is None:
            continue  # cannot assess heat without these; skip the hour
        hours.append(
            HourlyWeather(
                time=datetime.fromisoformat(t),
                temperature=float(temp),
                humidity=float(rh),
                solar=None if sw is None else float(sw),
                wind=None if wind is None else float(wind),
                precipitation=float(rain or 0.0),
            )
        )
    return Forecast(
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        elevation=raw.get("elevation"),
        utc_offset_seconds=int(raw.get("utc_offset_seconds", 19800)),
        hours=hours,
    )


def fetch(lat: float, lon: float) -> Forecast:
    return parse(fetch_raw(lat, lon))
