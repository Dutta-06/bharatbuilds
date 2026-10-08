"""get_surface: GET /surface?gpu_hours=4&gpu=a100&w_water=0.5&w_carbon=0.5&baseline=ap-south-1

The 48 h cost grid: for every region and hour, litres and kg CO2 for running
gpu_hours of work in that hour, and cost relative to running now in `baseline`.
Also GET /regions for region metadata.
"""

from backend import surface
from backend.http import handle, query_params, response
from model import regions as region_config

CACHE_SECONDS = 300


def regions_payload():
    return [{"id": r.id, "name": r.name, "geo": r.geo, "lat": r.lat, "lon": r.lon,
             "cooling_type": r.cooling_type, "zone": r.electricity_maps_zone,
             "water_stress_multiplier": r.stress_multiplier, "calibrated": r.calibrated}
            for r in region_config.load().values()]


@handle
def handler(event, context):
    if event.get("rawPath", "").rstrip("/").endswith("/regions"):
        return response(200, {"regions": regions_payload()}, cache_seconds=3600)

    payload = surface.build(query_params(event))
    if payload is None:
        return response(503, {"error": "no forecasts stored yet; run the forecast pipeline"})
    return response(200, payload, cache_seconds=CACHE_SECONDS)
