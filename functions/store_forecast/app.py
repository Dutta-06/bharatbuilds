"""store_forecast: write a region's 48 rows (the output of fetch_forecast) to DynamoDB.

Event:  {"region", "rows", "run_id"?}
Return: the META#latest marker

Also prints a CloudWatch Embedded Metric Format line (no extra permissions needed),
giving RowsWritten and ModelledCarbonHours per region for the dashboard.
"""

import json
import time

from backend import forecasts


def handler(event, context):
    meta = forecasts.store(event["region"], event["rows"], event.get("run_id"))
    modelled = sum(1 for r in event["rows"] if r.get("ci_source") == "modelled")
    print(json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "Pravaah", "Dimensions": [["Region"]],
            "Metrics": [{"Name": "RowsWritten", "Unit": "Count"},
                        {"Name": "ModelledCarbonHours", "Unit": "Count"}]}]},
        "Region": event["region"], "RowsWritten": meta["hours"], "ModelledCarbonHours": modelled,
    }))
    return meta
