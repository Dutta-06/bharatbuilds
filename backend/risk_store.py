"""Turn a forecast into stored risk rows, and stored rows back into a strip."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine import openmeteo
from engine.risk import STRIP_HOURS, assess_heat_hour, waterlogging_strip, window_from
from engine.thresholds import WORK_INTENSITIES
from engine.windows import HAZARDS, summarize

from . import cities, db

ROW_TTL = timedelta(days=2)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


def compute_rows(
    city_id: str,
    cell_id: str,
    raw_forecast: dict,
    now: datetime | None = None,
    run_id: str | None = None,
) -> tuple[list[dict], dict]:
    """(48 risk-hour items, run-marker item) for one cell. Nothing is written."""
    city = cities.city(city_id)
    cell = city.cell(cell_id)
    forecast = openmeteo.parse(raw_forecast)
    now = now or cities.local_now(city.timezone)
    lead_in, hours = window_from(forecast, now)

    computed_at = datetime.now(timezone.utc)
    run_id = run_id or computed_at.strftime("%Y-%m-%dT%H:00Z")
    offset = timedelta(seconds=forecast.utc_offset_seconds)

    water = waterlogging_strip(
        hours,
        has_hotspot=cell_id in cities.hotspot_cells(city_id),
        elevation_m=cell.elevation_m if cell.elevation_m is not None else forecast.elevation,
        city_ref_elevation_m=city.ref_elevation_m,
        lead_in=lead_in,
    )

    rows = []
    for hour, wl in zip(hours, water):
        per_work = {w: assess_heat_hour(hour, w) for w in WORK_INTENSITIES}
        first = per_work[WORK_INTENSITIES[0]]
        expires = (hour.time - offset).replace(tzinfo=timezone.utc) + ROW_TTL
        rows.append({
            "PK": db.cell_pk(city_id, cell_id),
            "SK": db.hour_sk(iso(hour.time)),
            "city": city_id,
            "cell_id": cell_id,
            "time": iso(hour.time),
            "heat": {
                "metric": first["metric"],
                "value": first["value"],
                **{w: per_work[w]["level"] for w in WORK_INTENSITIES},
            },
            "waterlogging": {"rain_mm": wl["value"], "level": wl["level"]},
            "run_id": run_id,
            "computed_at": computed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": int(expires.timestamp()),
        })

    meta = {
        "PK": db.cell_pk(city_id, cell_id),
        "SK": db.META_LATEST,
        "run_id": run_id,
        "computed_at": computed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_hour": rows[0]["time"] if rows else None,
        "last_hour": rows[-1]["time"] if rows else None,
        "hours": len(rows),
    }
    return rows, meta


def store(rows: list[dict], meta: dict) -> int:
    return db.put_items(rows + [meta])


def read_strip(
    city_id: str,
    cell_id: str,
    work: str,
    lang: str,
    now: datetime | None = None,
    hazards: tuple[str, ...] = HAZARDS,
) -> dict | None:
    """The next 48 hours for a cell as API output, or None if nothing is stored."""
    city = cities.city(city_id)
    start = cities.hour_floor(now or cities.local_now(city.timezone))
    end = start + timedelta(hours=STRIP_HOURS - 1)
    items = db.query_hours(city_id, cell_id, iso(start), iso(end))
    if not items:
        return None

    times = [datetime.fromisoformat(i["time"]) for i in items]
    out = {
        "hours": len(items),
        "complete": len(items) == STRIP_HOURS and times[0] == start,
        "computed_at": max(i["computed_at"] for i in items),
        "hazards": {},
    }
    for hazard in hazards:
        if hazard == "heat":
            strip = [{"time": i["time"], "level": i["heat"][work], "value": i["heat"]["value"],
                      "metric": i["heat"]["metric"]} for i in items]
        else:
            strip = [{"time": i["time"], "level": i["waterlogging"]["level"],
                      "value": i["waterlogging"]["rain_mm"], "metric": "rain_mm"} for i in items]
        levels = [s["level"] for s in strip]
        out["hazards"][hazard] = {
            **summarize(levels, times, work=work, hazard=hazard, lang=lang),
            "strip": strip,
        }
    return out
