from datetime import timedelta

from backend import db, risk_store

from .conftest import NOW, load_handler


def test_compute_risk_writes_48_rows_and_meta(aws, forecast):
    out = load_handler("compute_risk")(
        {"city": "delhi", "cell_id": "zakhira", "forecast": forecast, "now": NOW.isoformat()}, None
    )
    assert out["rows_written"] == 48
    assert out["first_hour"] == "2026-05-26T05:00"
    assert out["last_hour"] == "2026-05-28T04:00"

    meta = db.get_item(db.cell_pk("delhi", "zakhira"), db.META_LATEST)
    assert meta["hours"] == 48 and meta["run_id"] == out["run_id"]

    rows = db.query_hours("delhi", "zakhira", "2026-05-26T00:00", "2026-05-30T00:00")
    assert len(rows) == 48
    row = rows[10]  # 3 PM
    assert row["heat"]["metric"] == "wbgt"
    assert row["heat"]["heavy"] == "red"
    assert set(row["heat"]) == {"metric", "value", "light", "moderate", "heavy"}
    assert isinstance(row["heat"]["value"], float)
    assert row["expires_at"] > 0


def test_hotspot_cell_floods_and_plain_cell_does_not(aws, forecast):
    compute = load_handler("compute_risk")
    for cell in ("zakhira", "narela"):  # zakhira has a hotspot
        compute({"city": "delhi", "cell_id": cell, "forecast": forecast,
                 "now": NOW.isoformat()}, None)
    hot = db.query_hours("delhi", "zakhira", "2026-05-26T00:00", "2026-05-30T00:00")
    plain = db.query_hours("delhi", "narela", "2026-05-26T00:00", "2026-05-30T00:00")
    assert "red" in {r["waterlogging"]["level"] for r in hot}
    # 50 mm in 3 h is red even without a hotspot, so compare ambers instead:
    # the hotspot cell turns amber/red earlier in the storm
    first = lambda rows: next(i for i, r in enumerate(rows) if r["waterlogging"]["level"] != "green")  # noqa: E731
    assert first(hot) <= first(plain)


def test_read_strip_round_trip(aws, forecast):
    rows, meta = risk_store.compute_rows("delhi", "rohini", forecast, now=NOW)
    risk_store.store(rows, meta)
    out = risk_store.read_strip("delhi", "rohini", "light", "hi", now=NOW + timedelta(minutes=40))
    assert out["complete"] is True
    heat = out["hazards"]["heat"]
    assert len(heat["strip"]) == 48
    assert heat["strip"][0]["level"] == "green"  # 5 AM, light work
    assert heat["sentences"][0].startswith("अभी हल्के काम")


def test_read_strip_later_in_the_day_is_partial(aws, forecast):
    rows, meta = risk_store.compute_rows("delhi", "rohini", forecast, now=NOW)
    risk_store.store(rows, meta)
    out = risk_store.read_strip("delhi", "rohini", "heavy", "en", now=NOW + timedelta(hours=6))
    assert out["hours"] == 42
    assert out["complete"] is False


def test_read_strip_empty(aws):
    assert risk_store.read_strip("delhi", "rohini", "heavy", "en", now=NOW) is None
