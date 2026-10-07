"""store_forecast: write a region's 48 rows (the output of fetch_forecast) to DynamoDB.

Event:  {"region", "rows", "run_id"?}
Return: the META#latest marker
"""

from backend import forecasts


def handler(event, context):
    return forecasts.store(event["region"], event["rows"], event.get("run_id"))
