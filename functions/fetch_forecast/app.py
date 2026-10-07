"""fetch_forecast: call Open-Meteo for one cell and return the raw hourly data.

Event:  {"city": "delhi", "cell_id": "rohini"}
Return: {"city": ..., "cell_id": ..., "forecast": <Open-Meteo JSON>}
"""

from backend import cities
from engine import openmeteo


def handler(event, context):
    city = cities.city(event["city"])
    cell = city.cell(event["cell_id"])
    raw = openmeteo.fetch_raw(cell.lat, cell.lon)
    return {"city": city.id, "cell_id": cell.id, "forecast": raw}
