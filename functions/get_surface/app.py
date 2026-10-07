"""get_surface: GET /surface?gpu_hours=4&gpu=a100&w_water=0.5&w_carbon=0.5&baseline=ap-south-1

The 48 h cost grid: for every region and hour, litres and kg CO2 for running
gpu_hours of work in that hour, and cost relative to running now in `baseline`.
Also GET /regions for region metadata.
"""

from datetime import datetime, timedelta

from backend import forecasts
from backend.http import BadRequest, handle, query_params, response
from model import regions as region_config
from model.cost import Weights, cost
from model.energy import job_it_kwh

CACHE_SECONDS = 300


def _float(params, name, default, lo, hi):
    try:
        v = float(params.get(name, default))
    except ValueError:
        raise BadRequest(f"{name} must be a number") from None
    if not lo <= v <= hi:
        raise BadRequest(f"{name} must be between {lo} and {hi}")
    return v


def regions_payload():
    return [{"id": r.id, "name": r.name, "geo": r.geo, "lat": r.lat, "lon": r.lon,
             "cooling_type": r.cooling_type, "zone": r.electricity_maps_zone,
             "water_stress_multiplier": r.stress_multiplier, "calibrated": r.calibrated}
            for r in region_config.load().values()]


@handle
def handler(event, context):
    if event.get("rawPath", "").rstrip("/").endswith("/regions"):
        return response(200, {"regions": regions_payload()}, cache_seconds=3600)

    params = query_params(event)
    gpu_hours = _float(params, "gpu_hours", 1, 0.01, 10000)
    gpu = params.get("gpu", "a100")
    try:
        it_kwh = job_it_kwh(gpu_hours, gpu)
        weights = Weights(_float(params, "w_water", 0.5, 0, 1), _float(params, "w_carbon", 0.5, 0, 1))
    except ValueError as e:
        raise BadRequest(str(e)) from None
    baseline_id = params.get("baseline", "ap-south-1")
    known = region_config.load()
    if baseline_id not in known:
        raise BadRequest(f"baseline must be one of {', '.join(known)}")

    start = forecasts.utc_now_hour()
    surface, stored = forecasts.surface(start=start)
    if not surface.unit:
        return response(503, {"error": "no forecasts stored yet; run the forecast pipeline"})

    base = None
    if baseline_id in surface.unit and surface.covers(baseline_id, start, 1):
        base = (surface.window(baseline_id, start, 1, it_kwh), known[baseline_id])

    hours = sorted({h for t in surface.unit.values() for h in t})
    out_regions, best = [], None
    for rid, table in surface.unit.items():
        meta = {r["hour"]: r for r in stored.get(rid, [])}
        cells = []
        for h in sorted(table):
            fp = surface.window(rid, datetime.strptime(h, "%Y-%m-%dT%H:00"), 1, it_kwh)
            c = cost(fp, known[rid], weights, baseline=base)
            row = meta.get(h, {})
            cells.append({"hour": h, "cost": round(c, 4), "litres": round(fp.litres, 3),
                          "litres_low": round(fp.litres_low, 3), "litres_high": round(fp.litres_high, 3),
                          "kg_co2": round(fp.kg_co2, 4), "kg_low": round(fp.kg_low, 4),
                          "kg_high": round(fp.kg_high, 4), "t_wb": round(fp.t_wb, 1),
                          "ci": row.get("ci_g_per_kwh"), "ci_source": row.get("ci_source")})
            if best is None or c < best["cost"]:
                best = {"region": rid, "hour": h, "cost": round(c, 4)}
        r = known[rid]
        latest = forecasts.latest_meta(rid) or {}
        out_regions.append({"id": rid, "name": r.name, "lat": r.lat, "lon": r.lon, "geo": r.geo,
                            "forecast_error": latest.get("error"), "run_id": latest.get("run_id"),
                            "t_wb_sources": latest.get("t_wb_sources", []),
                            "weather_sources": sorted({x.get("weather_source") for x in meta.values()}),
                            "ci_sources": sorted({x.get("ci_source") for x in meta.values()}),
                            "cells": cells})

    return response(200, {
        "gpu_hours": gpu_hours, "gpu": gpu, "it_kwh": round(it_kwh, 4),
        "weights": {"water": weights.water, "carbon": weights.carbon},
        "baseline": {"region": baseline_id, "hour": forecasts.key(start)} if base else None,
        "hours": hours, "regions": out_regions, "best": best,
        "window_end": forecasts.key(start + timedelta(hours=forecasts.HOURS - 1)),
    }, cache_seconds=CACHE_SECONDS)
