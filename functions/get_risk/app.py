"""get_risk: GET /risk?lat=&lon=&work=&lang=   (or ?city=&cell= instead of lat/lon)

Finds the nearest cell and returns the next 48 hours for both hazards, with
plain-language safe windows.
"""

from backend import cities, risk_store
from backend.http import BadRequest, error, handle, query_params, response
from engine.thresholds import WORK_INTENSITIES
from engine.windows import languages

CACHE_SECONDS = 300  # CloudFront caches GET /risk for 5 minutes (Step 5)


def parse_float(params: dict, name: str, lo: float, hi: float) -> float:
    try:
        value = float(params[name])
    except KeyError:
        raise BadRequest(f"{name} is required") from None
    except ValueError:
        raise BadRequest(f"{name} must be a number") from None
    if not lo <= value <= hi:
        raise BadRequest(f"{name} must be between {lo} and {hi}")
    return value


@handle
def handler(event, context):
    params = query_params(event)
    work = params.get("work", "heavy")
    lang = params.get("lang", "en")
    if work not in WORK_INTENSITIES:
        raise BadRequest(f"work must be one of {', '.join(WORK_INTENSITIES)}")
    if lang not in languages():
        raise BadRequest(f"lang must be one of {', '.join(languages())}")

    distance_km = 0.0
    if "city" in params or "cell" in params:
        try:
            city = cities.city(params.get("city", ""))
            cell = city.cell(params.get("cell", ""))
        except KeyError:
            raise BadRequest("unknown city or cell", status=404) from None
    else:
        lat = parse_float(params, "lat", -90, 90)
        lon = parse_float(params, "lon", -180, 180)
        found = cities.locate(lat, lon)
        if found is None:
            raise BadRequest("this location is outside the cities Chhaanv covers", status=404)
        city, cell, distance_km = found

    result = risk_store.read_strip(city.id, cell.id, work, lang)
    if result is None:
        return error(503, f"no risk data for {cell.name} yet; the hourly pipeline has not run")

    return response(200, {
        "city": {"id": city.id, "name": city.name},
        "cell": {"id": cell.id, "name": cell.name, "name_hi": cell.name_hi,
                 "lat": cell.lat, "lon": cell.lon, "distance_km": round(distance_km, 2)},
        "work": work,
        "lang": lang,
        **result,
    }, cache_seconds=CACHE_SECONDS)
