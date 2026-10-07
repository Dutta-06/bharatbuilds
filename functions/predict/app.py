"""predict: Step 4 models in the forecast pipeline, between fetch and store.

Event:  {"region", "rows"}    (rows from fetch_forecast)
Return: {"rows"}              (model-corrected where a model beat its baselines,
                               otherwise unchanged; each row says which source it used)
"""

from datetime import datetime, timedelta

from backend import db
from forecasting import serve


def yesterday_ci(region: str, rows: list[dict]) -> dict:
    """Stored values for the same hours 24 h earlier, keyed by the *target* hour."""
    if not rows:
        return {}
    fmt = "%Y-%m-%dT%H:00"
    first = datetime.strptime(rows[0]["hour"], fmt) - timedelta(hours=24)
    last = datetime.strptime(rows[-1]["hour"], fmt) - timedelta(hours=24)
    stored = db.forecast_hours(region, first.strftime(fmt), last.strftime(fmt))
    return {(datetime.strptime(r["hour"], fmt) + timedelta(hours=24)).strftime(fmt): r["ci_g_per_kwh"] for r in stored}


def handler(event, context):
    region, rows = event["region"], event["rows"]
    yesterday = yesterday_ci(region, rows) if serve.load(region, "ci") else {}
    return {"rows": serve.apply(region, rows, yesterday)}
