"""Team policies (Step 12): default weights, allowed regions, residency and max delay per team.

A platform lead (Cognito group `platform-leads`) edits a team's policy; any job that
names that team is placed under it. The job may narrow allowed regions further but
cannot widen them, and the team's weights replace the job's.
"""

from __future__ import annotations

from datetime import datetime, timezone

from model import regions as region_config

from . import db
from .http import BadRequest

LEAD_GROUP = "platform-leads"


def get(team: str) -> dict | None:
    item = db.get_item(db.policy_pk(team), db.META)
    return {k: v for k, v in item.items() if k not in ("PK", "SK")} if item else None


def validate(team: str, body: dict) -> dict:
    known = set(region_config.load())
    w = body.get("weights") or {}
    try:
        water, carbon = float(w.get("water", 0.5)), float(w.get("carbon", 0.5))
    except (TypeError, ValueError):
        raise BadRequest("weights must be numbers") from None
    if water < 0 or carbon < 0 or water + carbon == 0:
        raise BadRequest("weights must be non-negative and not both zero")
    allowed = body.get("allowed_regions")
    if allowed is not None and (not isinstance(allowed, list) or not allowed or not set(allowed) <= known):
        raise BadRequest(f"allowed_regions must be a non-empty list from {', '.join(sorted(known))}")
    max_delay = body.get("max_delay_h")
    if max_delay is not None:
        try:
            max_delay = float(max_delay)
        except (TypeError, ValueError):
            raise BadRequest("max_delay_h must be a number") from None
        if not 0 <= max_delay <= 720:
            raise BadRequest("max_delay_h must be between 0 and 720")
    return {"team": team, "weights": {"water": water, "carbon": carbon}, "allowed_regions": allowed,
            "data_residency": bool(body.get("data_residency", False)), "max_delay_h": max_delay}


def put(team: str, body: dict, updated_by: str) -> dict:
    policy = validate(team, body)
    policy.update(updated_by=updated_by, updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    db.put_item({"PK": db.policy_pk(team), "SK": db.META, **policy})
    return policy


def apply(body: dict) -> dict:
    """Return the job body with the named team's policy applied (no team: unchanged)."""
    team = body.get("team")
    if not team:
        return body
    policy = get(str(team))
    if policy is None:
        raise BadRequest(f"no policy for team {team!r}", status=404)
    out = dict(body)
    out["weights"] = policy["weights"]
    if policy.get("allowed_regions"):
        allowed = set(policy["allowed_regions"])
        if body.get("allowed_regions"):
            allowed &= set(body["allowed_regions"])
            if not allowed:
                raise BadRequest("allowed_regions do not overlap the team policy")
        out["allowed_regions"] = sorted(allowed)
    out["data_residency"] = bool(body.get("data_residency")) or policy.get("data_residency", False)
    if policy.get("max_delay_h") is not None:
        out["max_delay_h"] = min(float(body.get("max_delay_h", policy["max_delay_h"])), policy["max_delay_h"])
    out["policy_applied"] = {"team": team, "updated_at": policy.get("updated_at")}
    return out
