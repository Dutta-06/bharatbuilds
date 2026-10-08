"""get_savings: GET /savings?team=ml&days=30

Litres and kg CO2 saved by Pravaah placements, per day (cumulative) and per team.
"""

from backend import savings
from backend.http import BadRequest, handle, query_params, response


@handle
def handler(event, context):
    params = query_params(event)
    try:
        days = int(params.get("days", 30))
    except ValueError:
        raise BadRequest("days must be a whole number") from None
    if not 1 <= days <= 365:
        raise BadRequest("days must be between 1 and 365")
    return response(200, savings.build(team=params.get("team") or None, days=days), cache_seconds=60)
