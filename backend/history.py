"""Weather and grid history per region, shared by scripts/pull_history.py and the collect_history Lambda.

The free Electricity Maps tier returns only the last 24 h of carbon history, so real history
exists only if something collects it continuously. collect_history does that into S3
(history/<region>.csv, same columns as data/history/*.csv) and merges, never discarding real hours.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timedelta

from model.wetbulb import wet_bulb
from sources import openmeteo
from sources.carbon import CarbonSourceError, ElectricityMaps, ModelledProfile

COLUMNS = ["hour", "t_db", "rh", "p_hpa", "t_wb", "ci_g_per_kwh", "ci_source", "mix_json"]


def rows_for(region, days: int, now: datetime) -> list[dict]:
    if days <= 92:
        weather = openmeteo.recent(region.lat, region.lon, days)   # up to now, overlaps carbon history
    else:
        end = now - timedelta(days=6)                               # archive lags ~5 days
        weather = openmeteo.history(region.lat, region.lon, end - timedelta(days=days - 1), end)
    profile = ModelledProfile(region.typical_ci_g_per_kwh or 0.0, region.grid_mix, region.lon)
    real = {}
    if region.electricity_maps_zone:
        try:
            real = {g.hour: g for g in ElectricityMaps().history(region.electricity_maps_zone)}
        except CarbonSourceError as e:
            print(f"  {region.id}: Electricity Maps unavailable ({e}); using modelled carbon", file=sys.stderr)
    out = []
    for t, temp, rh, p in weather:
        hour = t[:13] + ":00"
        g = real.get(hour) or profile.at(datetime.strptime(hour, "%Y-%m-%dT%H:00"))
        out.append({
            "hour": hour, "t_db": temp, "rh": rh, "p_hpa": p,
            "t_wb": round(wet_bulb(temp, max(rh, 1), p), 2),
            "ci_g_per_kwh": g.ci_g_per_kwh, "ci_source": g.source,
            "mix_json": json.dumps(g.mix or region.grid_mix, separators=(",", ":")),
        })
    return out


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def from_csv(text: str) -> list[dict]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        for k in ("t_db", "rh", "p_hpa", "t_wb", "ci_g_per_kwh"):
            r[k] = float(r[k])
        rows.append(r)
    return rows


def merge(existing: list[dict], new: list[dict]) -> list[dict]:
    """Union by hour. A real carbon hour is never replaced by a modelled one; otherwise the newer row wins."""
    by_hour = {r["hour"]: r for r in existing}
    for r in new:
        old = by_hour.get(r["hour"])
        if old and old["ci_source"] != "modelled" and r["ci_source"] == "modelled":
            continue
        by_hour[r["hour"]] = r
    return [by_hour[h] for h in sorted(by_hour)]
