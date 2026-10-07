"""City lookup and local time, cached per Lambda container."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from engine import grid

# India has one time zone with no DST, so a fixed offset is a safe fallback if
# the runtime has no tz database.
FALLBACK_OFFSETS = {"Asia/Kolkata": timedelta(hours=5, minutes=30)}


@lru_cache(maxsize=None)
def city(city_id: str) -> grid.City:
    try:
        return grid.load_city(city_id)
    except FileNotFoundError:
        raise KeyError(city_id) from None


@lru_cache(maxsize=None)
def hotspot_cells(city_id: str) -> frozenset[str]:
    return frozenset(grid.hotspot_cells(city_id))


@lru_cache(maxsize=1)
def all_cities() -> tuple[grid.City, ...]:
    return tuple(city(cid) for cid in grid.city_ids())


def locate(lat: float, lon: float) -> tuple[grid.City, grid.Cell, float] | None:
    """(city, nearest cell, km) for a point, or None if no city covers it."""
    best = None
    for c in all_cities():
        if c.contains(lat, lon):
            cell, km = c.nearest(lat, lon)
            if best is None or km < best[2]:
                best = (c, cell, km)
    return best


def local_now(tz_name: str, now_utc: datetime | None = None) -> datetime:
    """Current local time as a naive datetime (how risk rows are keyed)."""
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        return now_utc.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
    except Exception:  # zoneinfo missing or tz database not installed
        offset = FALLBACK_OFFSETS.get(tz_name)
        if offset is None:
            raise
        return (now_utc + offset).replace(tzinfo=None)


def hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)
