"""Cumulative savings over time, from job placements: GET /savings[?team=ml&days=30].

Every feasible job has a modelled receipt (chosen placement versus running immediately in its
submit region). `done` jobs have run, so their savings are realised; the rest are scheduled.
All figures are modelled, as the receipts say; only the stand-in workload's energy is measured.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from . import forecasts, jobs

UNASSIGNED = "unassigned"
MAX_JOBS = 1000


def _saved(job: dict) -> tuple[float, float] | None:
    r = job.get("preview_receipt")
    if not r:
        return None
    return (r["baseline"]["litres"] - r["chosen"]["litres"], r["baseline"]["kg_co2"] - r["chosen"]["kg_co2"])


def summarise(items: list[dict], team: str | None = None, days: int = 30,
              now: datetime | None = None) -> dict:
    now = now or forecasts.utc_now()
    first = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    per_day: dict[str, dict] = defaultdict(lambda: {"jobs": 0, "litres": 0.0, "kg_co2": 0.0})
    per_team: dict[str, dict] = defaultdict(lambda: {"jobs": 0, "done": 0, "litres": 0.0, "kg_co2": 0.0})
    for job in items:
        s = _saved(job)
        who = job.get("team") or UNASSIGNED
        if s is None or (team and who != team):
            continue
        day = job["submitted_at"][:10]
        if day < first:
            continue
        for bucket in (per_day[day], per_team[who]):
            bucket["jobs"] += 1
            bucket["litres"] += s[0]
            bucket["kg_co2"] += s[1]
        per_team[who]["done"] += job["status"] == "done"

    daily, cum_l, cum_kg, cum_jobs = [], 0.0, 0.0, 0
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        x = per_day.get(d, {"jobs": 0, "litres": 0.0, "kg_co2": 0.0})
        cum_l += x["litres"]; cum_kg += x["kg_co2"]; cum_jobs += x["jobs"]
        daily.append({"date": d, "jobs": x["jobs"], "litres_saved": round(x["litres"], 3),
                      "kg_co2_saved": round(x["kg_co2"], 4), "cumulative_litres_saved": round(cum_l, 3),
                      "cumulative_kg_co2_saved": round(cum_kg, 4), "cumulative_jobs": cum_jobs})
    teams = sorted(({"team": t, "jobs": v["jobs"], "done": v["done"], "litres_saved": round(v["litres"], 3),
                     "kg_co2_saved": round(v["kg_co2"], 4)} for t, v in per_team.items()),
                   key=lambda r: -r["litres_saved"])
    return {
        "days": days, "team": team,
        "totals": {"jobs": cum_jobs, "done": sum(t["done"] for t in teams),
                   "litres_saved": round(cum_l, 3), "kg_co2_saved": round(cum_kg, 4)},
        "by_team": teams, "daily": daily,
        "note": "Modelled: each job's chosen placement versus running it immediately in its submit region.",
    }


def build(team: str | None = None, days: int = 30, now: datetime | None = None) -> dict:
    return summarise(jobs.queue(MAX_JOBS), team=team, days=days, now=now)
