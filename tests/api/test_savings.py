from datetime import datetime, timezone

import pytest

from backend import policies, savings

from .conftest import body, http, load_handler


def job(day, team, litres_saved, kg_saved, status="placed"):
    return {"submitted_at": f"{day}T10:00:00Z", "team": team, "status": status,
            "preview_receipt": {"baseline": {"litres": 10 + litres_saved, "kg_co2": 1 + kg_saved},
                                "chosen": {"litres": 10, "kg_co2": 1}}}


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


def test_cumulative_by_day_and_team():
    items = [job("2026-10-08", "ml", 2.0, 0.2, "done"), job("2026-10-08", None, 1.0, 0.1),
             job("2026-10-10", "ml", 3.0, 0.3), {"submitted_at": "2026-10-09T01:00:00Z", "status": "infeasible"}]
    out = savings.summarise(items, days=3, now=NOW)
    assert [d["date"] for d in out["daily"]] == ["2026-10-08", "2026-10-09", "2026-10-10"]
    assert [d["cumulative_litres_saved"] for d in out["daily"]] == [3.0, 3.0, 6.0]
    assert out["totals"] == {"jobs": 3, "done": 1, "litres_saved": 6.0, "kg_co2_saved": 0.6}
    assert out["by_team"][0] == {"team": "ml", "jobs": 2, "done": 1, "litres_saved": 5.0, "kg_co2_saved": 0.5}
    assert {t["team"] for t in out["by_team"]} == {"ml", "unassigned"}


def test_team_filter_and_window():
    items = [job("2026-10-01", "ml", 9.0, 0.9), job("2026-10-09", "ml", 2.0, 0.2), job("2026-10-09", "ops", 5.0, 0.5)]
    out = savings.summarise(items, team="ml", days=3, now=NOW)
    assert out["totals"]["litres_saved"] == 2.0 and [t["team"] for t in out["by_team"]] == ["ml"]


def test_endpoint(seeded):
    policies.put("ml", {"weights": {"water": 1.0, "carbon": 0.0}}, "test")
    assert load_handler("submit_job")(http(body={"gpu_hours": 4, "deadline_h": 24, "team": "ml"}), None)["statusCode"] == 201
    resp = load_handler("get_savings")(http({"days": "7"}), None)
    assert resp["statusCode"] == 200
    b = body(resp)
    assert len(b["daily"]) == 7 and b["totals"]["jobs"] == 1 and b["by_team"][0]["team"] == "ml"
    assert load_handler("get_savings")(http({"days": "abc"}), None)["statusCode"] == 400
    assert load_handler("get_savings")(http({"days": "0"}), None)["statusCode"] == 400
