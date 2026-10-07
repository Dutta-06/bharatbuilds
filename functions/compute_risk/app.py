"""compute_risk: run the engine for one cell and write 48 hourly rows.

Event:  the output of fetch_forecast, {"city", "cell_id", "forecast"},
        optionally with "now" (local ISO) and "run_id".
Return: {"city", "cell_id", "run_id", "rows_written", "first_hour", "last_hour"}
"""

from datetime import datetime

from backend import risk_store


def handler(event, context):
    now = datetime.fromisoformat(event["now"]) if event.get("now") else None
    rows, meta = risk_store.compute_rows(
        event["city"], event["cell_id"], event["forecast"], now=now, run_id=event.get("run_id")
    )
    risk_store.store(rows, meta)
    return {
        "city": event["city"],
        "cell_id": event["cell_id"],
        "run_id": meta["run_id"],
        "rows_written": len(rows),
        "first_hour": meta["first_hour"],
        "last_hour": meta["last_hour"],
    }
