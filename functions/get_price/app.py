"""get_price: GET /price?region=ap-south-1&hour=2026-10-10T09:00   (public, throttled)

"The water price of compute": litres and kg CO2 per GPU-hour (A100 by default) and
per kWh of IT energy, for one region and UTC hour within the stored 48 h forecast.
"""

from datetime import datetime

from backend import forecasts
from backend.http import BadRequest, error, handle, query_params, response
from model import regions as region_config
from model.cost import footprint
from model.energy import job_it_kwh


@handle
def handler(event, context):
    params = query_params(event)
    region_id = params.get("region", "")
    known = region_config.load()
    if region_id not in known:
        raise BadRequest(f"region must be one of {', '.join(known)}")
    hour = params.get("hour")
    try:
        when = datetime.strptime(hour[:13], "%Y-%m-%dT%H") if hour else forecasts.utc_now_hour()
    except ValueError:
        raise BadRequest("hour must look like 2026-10-10T09:00 (UTC)") from None
    gpu = params.get("gpu", "a100")
    try:
        per_gpu_hour_kwh = job_it_kwh(1, gpu)
    except ValueError as e:
        raise BadRequest(str(e)) from None
    rows = forecasts.load(start=when, hours=1, region_ids=[region_id])[region_id]
    if not rows:
        return error(404, f"no forecast for {region_id} at {forecasts.key(when)} (the stored window is the next 48 h)")
    row = rows[0]
    fp = footprint(known[region_id], forecasts.to_conditions(rows)[0], 1.0)
    per_kwh = {"litres": round(fp.litres, 4), "litres_low": round(fp.litres_low, 4), "litres_high": round(fp.litres_high, 4),
               "kg_co2": round(fp.kg_co2, 5), "litres_site": round(fp.litres_site, 4), "litres_grid": round(fp.litres_grid, 4)}
    per_gpu_hour = {k: round(v * per_gpu_hour_kwh, 5) for k, v in per_kwh.items()}
    return response(200, {
        "region": region_id, "hour": forecasts.key(when), "gpu": gpu,
        "per_kwh_it": per_kwh, "per_gpu_hour": per_gpu_hour,
        "inputs": {"t_wb": round(fp.t_wb, 2), "ci_g_per_kwh": row["ci_g_per_kwh"], "ci_source": row["ci_source"],
                   "weather_source": row["weather_source"]},
        "docs": "https://github.com/Dutta-06/bharatbuilds/blob/main/docs/api.md",
    }, cache_seconds=300)
