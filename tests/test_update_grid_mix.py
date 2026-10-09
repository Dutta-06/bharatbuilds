import json
import sys

import pytest
import yaml

from tests.api.conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import update_grid_mix as g  # noqa: E402


def row(hour, ci, mix, source="electricitymaps"):
    return {"hour": hour, "ci_g_per_kwh": ci, "ci_source": source, "mix_json": json.dumps(mix)}


def test_summarise_weights_by_megawatts_and_ignores_modelled_hours():
    rows = [row("2026-10-01T00:00", "100", {"coal": 300, "wind": 100}), row("2026-10-01T01:00", "200", {"coal": 100, "wind": 300}),
            row("2026-10-01T02:00", "999", {"gas": 1}, source="modelled")]
    s = g.summarise(rows)
    assert s["shares"] == {"coal": 0.5, "wind": 0.5} and s["ci"] == 150 and s["hours"] == 2
    assert abs(sum(s["shares"].values()) - 1) < 1e-9
    assert g.summarise([row("2026-10-01T02:00", "1", {"gas": 1}, source="modelled")]) is None


def test_shares_always_sum_to_one_after_rounding():
    s = g.summarise([row("2026-10-01T00:00", "100", {"a": 1, "b": 1, "c": 1})])
    assert abs(sum(s["shares"].values()) - 1) < 1e-9


def test_apply_changes_only_the_named_region_and_records_the_window():
    text = (ROOT / "data" / "regions.yaml").read_text(encoding="utf-8")
    s = g.summarise([row("2026-10-01T00:00", "26", {"hydro": 40, "wind": 35, "nuclear": 25}), row("2026-10-03T00:00", "30", {"hydro": 40, "wind": 35, "nuclear": 25})])
    out = g.apply(text, "eu-north-1", s)
    regions = {r["id"]: r for r in yaml.safe_load(out)["regions"]}
    assert regions["eu-north-1"]["grid_mix"] == {"placeholder": False, "shares": {"hydro": 0.4, "wind": 0.35, "nuclear": 0.25}}
    assert regions["eu-north-1"]["typical_ci_g_per_kwh"] == 28
    assert regions["ap-south-1"]["grid_mix"]["placeholder"] is True                     # untouched
    assert "mean of 2 real Electricity Maps hours, 2026-10-01 to 2026-10-03; not an annual figure" in out
    assert out.startswith("# AWS regions")                                               # comments survive


def test_unknown_region_is_an_error():
    with pytest.raises(ValueError):
        g.apply("regions:\n  - id: a-b-1\n", "x-y-1", {"shares": {"a": 1.0}, "ci": 1, "hours": 1, "first": "2026-01-01T00:00", "last": "2026-01-01T00:00"})
