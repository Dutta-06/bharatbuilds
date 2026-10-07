"""subscribe: POST /subscribe

Body: {"device_id": "...", "lat": .., "lon": ..   (or "city" + "cell_id"),
       "work": "heavy", "lang": "hi", "hazards": ["heat", "waterlogging"],
       "channel": "email", "contact": "someone@example.com"}

Stores one subscription per (device, cell). Re-subscribing to the same cell
replaces the earlier one. Email delivery and confirmation come in Step 7.
"""

import re
import uuid
from datetime import datetime, timezone

from backend import cities, db
from backend.http import BadRequest, handle, json_body, response
from engine.thresholds import WORK_INTENSITIES
from engine.windows import HAZARDS, languages

CHANNELS = ("email", "webpush")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def mask(contact: str) -> str:
    name, _, domain = contact.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


@handle
def handler(event, context):
    body = json_body(event)

    device_id = body.get("device_id") or uuid.uuid4().hex
    if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
        raise BadRequest("device_id must be 8-64 letters, digits, - or _")

    if body.get("city") or body.get("cell_id"):
        try:
            city = cities.city(str(body.get("city", "")))
            cell = city.cell(str(body.get("cell_id", "")))
        except KeyError:
            raise BadRequest("unknown city or cell_id", status=404) from None
    else:
        try:
            lat, lon = float(body["lat"]), float(body["lon"])
        except (KeyError, TypeError, ValueError):
            raise BadRequest("give either city + cell_id, or numeric lat + lon") from None
        found = cities.locate(lat, lon)
        if found is None:
            raise BadRequest("this location is outside the cities Chhaanv covers", status=404)
        city, cell, _ = found

    work = body.get("work", "heavy")
    if work not in WORK_INTENSITIES:
        raise BadRequest(f"work must be one of {', '.join(WORK_INTENSITIES)}")
    lang = body.get("lang", "hi")
    if lang not in languages():
        raise BadRequest(f"lang must be one of {', '.join(languages())}")
    hazards = body.get("hazards", list(HAZARDS))
    if not isinstance(hazards, list) or not hazards or not set(hazards) <= set(HAZARDS):
        raise BadRequest(f"hazards must be a non-empty list from {', '.join(HAZARDS)}")

    channel = body.get("channel", "email")
    if channel not in CHANNELS:
        raise BadRequest(f"channel must be one of {', '.join(CHANNELS)}")
    contact = body.get("contact")
    if channel == "email":
        contact = contact.strip().lower() if isinstance(contact, str) else ""
        if len(contact) > 254 or not EMAIL_RE.match(contact):
            raise BadRequest("contact must be a valid email address")
    elif not isinstance(contact, (str, dict)) or not contact:
        raise BadRequest("contact must be the web push subscription")

    db.put_items([{
        "PK": db.user_pk(device_id),
        "SK": db.sub_sk(city.id, cell.id),
        "GSI1PK": db.subs_gsi_pk(city.id, cell.id),
        "GSI1SK": db.user_pk(device_id),
        "city": city.id,
        "cell_id": cell.id,
        "work": work,
        "lang": lang,
        "hazards": sorted(set(hazards)),
        "channel": channel,
        "contact": contact,
        "status": "pending_confirmation" if channel == "email" else "active",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }])

    return response(201, {
        "device_id": device_id,
        "city": city.id,
        "cell": {"id": cell.id, "name": cell.name, "name_hi": cell.name_hi},
        "work": work,
        "lang": lang,
        "hazards": sorted(set(hazards)),
        "channel": channel,
        "contact": mask(contact) if channel == "email" else "web push",
        "status": "pending_confirmation" if channel == "email" else "active",
    })
