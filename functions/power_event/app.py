"""IoT and EventBridge entry points share the same facility domain logic."""
import logging
from backend import facilities
from backend.http import BadRequest

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def handler(event, context):
    if event.get("source") == "aws.events":
        # Bounded hackathon registry: facilities are explicitly indexed, not inferred from regions.
        from backend import db
        from boto3.dynamodb.conditions import Key
        for f in db.query(Key("GSI1PK").eq("FACILITIES"), index="GSI1"):
            facilities.reevaluate(f["facility_id"])
        return {"reevaluated": True}
    topic_facility = event.pop("topic_facility", None)
    if topic_facility and topic_facility != event.get("facility_id"):
        raise ValueError("MQTT topic and payload facility mismatch")
    try:
        result = facilities.process_event(event)
        log.info("power_event %s", result)
        return result
    except BadRequest as exc:
        # Invalid telemetry is durable in CloudWatch; transient infrastructure errors are raised for retry.
        log.warning("rejected_power_event status=%s reason=%s event=%s", exc.status, exc, event)
        if exc.status == 409 and "concurrent" in str(exc):
            raise
        return {"rejected": True, "status": exc.status, "reason": str(exc)}
