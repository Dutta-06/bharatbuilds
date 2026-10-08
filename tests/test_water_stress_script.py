import sys

import pytest

from tests.api.conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import set_water_stress as ws  # noqa: E402


def test_sets_only_the_named_region_and_keeps_comments():
    text = (ROOT / "data" / "regions.yaml").read_text(encoding="utf-8")
    out = ws.apply(text, {"eu-north-1": 0.4})
    assert out.count("water_stress_score: 0.4") == 1
    assert out.count("water_stress_score: null") == text.count("water_stress_score: null") - 1
    assert out.startswith("# AWS regions Pravaah can place jobs in.")
    import yaml
    scores = {r["id"]: r["water_stress_score"] for r in yaml.safe_load(out)["regions"]}
    assert scores["eu-north-1"] == 0.4 and scores["ap-south-1"] is None


@pytest.mark.parametrize("bad", [{"eu-north-1": 6}, {"eu-north-1": -1}, {"nowhere": 1}])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        ws.apply((ROOT / "data" / "regions.yaml").read_text(encoding="utf-8"), bad)
