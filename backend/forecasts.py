"""Forecast rows: collect (weather + grid), store in DynamoDB, load back as a cost surface."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from model import regions as region_config
from model.cost import Conditions
from model.wetbulb import wet_bulb
from scheduler.surface import Surface, build
from sources import grid, openmeteo, synthetic

from . import db

HOURS = 48
ROW_TTL = timedelta(days=3)


def utc_now() -> datetime:
    """The one clock the backend reads (tests freeze it)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_hour() -> datetime:
    return utc_now().replace(minute=0, second=0, microsecond=0)


def key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:00")


def collect(region_id: str, start: datetime | None = None, hours: int = HOURS,
            offline: bool = False) -> list[dict]:
    """48 hourly rows for one region: weather, wet-bulb, carbon intensity and mix, with sources."""
    region = region_config.get(region_id)
    start = start or utc_now_hour()
    if offline:
        weather, wsource = synthetic.weather(region_id, start, hours), "synthetic"
    else:
        weather, wsource = openmeteo.forecast(region.lat, region.lon, hours), "open-meteo"
    grid_hours = {g.hour: g for g in grid.outlook(region, start, hours)}
    rows = []
    for t, temp, rh, p in weather:
        g = grid_hours.get(t)
        if g is None:
            continue
        rows.append({
            "hour": t, "t_db": temp, "rh": rh, "p_hpa": p,
            "t_wb": round(wet_bulb(temp, max(rh, 1.0), p), 2),
            "ci_g_per_kwh": g.ci_g_per_kwh, "ci_source": g.source,
            "mix": g.mix or region.grid_mix, "weather_source": wsource,
        })
    return rows


NOWCAST_HOURS = 3


def score_previous(region_id: str, rows: list[dict]) -> dict | None:
    """Forecast error of the previous run, judged on this run's first hours.

    The first NOWCAST_HOURS of a fresh run are close to observed conditions, so the
    previous run's predictions for those hours (made at least an hour earlier) are
    scored against them: a cheap, always-available proxy for MAE against observations.
    """
    if not rows:
        return None
    first, last = rows[0]["hour"], rows[min(NOWCAST_HOURS, len(rows)) - 1]["hour"]
    old = {r["hour"]: r for r in db.forecast_hours(region_id, first, last)}
    pairs = [(old[r["hour"]], r) for r in rows[:NOWCAST_HOURS] if r["hour"] in old]
    if not pairs:
        return None
    return {
        "basis": f"previous run vs this run's first {NOWCAST_HOURS} h (nowcast proxy)",
        "n": len(pairs),
        "mae_t_wb": round(sum(abs(o["t_wb"] - n["t_wb"]) for o, n in pairs) / len(pairs), 3),
        "mae_ci": round(sum(abs(o["ci_g_per_kwh"] - n["ci_g_per_kwh"]) for o, n in pairs) / len(pairs), 2),
        "previous_run_id": pairs[0][0].get("run_id"),
    }


def store(region_id: str, rows: list[dict], run_id: str | None = None) -> dict:
    """Score the previous run, write rows plus a META#latest marker; returns the marker."""
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    error = score_previous(region_id, rows)
    items = []
    for r in rows:
        expires = datetime.strptime(r["hour"], "%Y-%m-%dT%H:00").replace(tzinfo=timezone.utc) + ROW_TTL
        items.append({"PK": db.forecast_pk(region_id), "SK": db.hour_sk(r["hour"]),
                      "region": region_id, "run_id": run_id, "expires_at": int(expires.timestamp()), **r})
    meta = {"PK": db.forecast_pk(region_id), "SK": db.META_LATEST, "region": region_id, "run_id": run_id,
            "first_hour": rows[0]["hour"] if rows else None, "last_hour": rows[-1]["hour"] if rows else None,
            "hours": len(rows), "ci_sources": sorted({r["ci_source"] for r in rows}),
            "weather_sources": sorted({r["weather_source"] for r in rows}),
            "t_wb_sources": sorted({r.get("t_wb_source", "provider") for r in rows}),
            "error": error}
    extra = [{"PK": db.forecast_pk(region_id), "SK": f"ERROR#{run_id}", "region": region_id, "run_id": run_id,
              "expires_at": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()), **error}] if error else []
    db.put_items(items + [meta] + extra)
    return meta


def latest_meta(region_id: str) -> dict | None:
    return db.get_item(db.forecast_pk(region_id), db.META_LATEST)


def load(start: datetime | None = None, hours: int = HOURS, region_ids=None) -> dict[str, list[dict]]:
    start = start or utc_now_hour()
    end = start + timedelta(hours=hours - 1)
    ids = region_ids or list(region_config.load())
    return {rid: db.forecast_hours(rid, key(start), key(end)) for rid in ids}


def to_conditions(rows: list[dict]) -> list[Conditions]:
    return [Conditions(hour=r["hour"], t_db=r["t_db"], rh=r["rh"], ci_g_per_kwh=r["ci_g_per_kwh"],
                       p_hpa=r["p_hpa"], grid_mix=r.get("mix") or None,
                       t_wb=r["t_wb"] if r.get("t_wb_source") == "model" else None) for r in rows]


def surface(start: datetime | None = None, hours: int = HOURS, region_ids=None) -> tuple[Surface, dict]:
    """Cost surface from stored forecasts, plus per-region row metadata for display."""
    stored = load(start, hours, region_ids)
    regions = region_config.load()
    s = build(regions, {rid: to_conditions(rows) for rid, rows in stored.items() if rows})
    return s, stored


def offline_default() -> bool:
    return os.environ.get("PRAVAAH_OFFLINE", "").lower() in ("1", "true", "yes")
