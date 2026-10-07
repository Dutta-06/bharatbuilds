import math
import random
from datetime import datetime, timedelta

import pytest

pytest.importorskip("sklearn")  # training-only dependency; serving needs none

from forecasting.evaluate import fit_and_judge  # noqa: E402
from forecasting.features import CARBON_FEATURES, WETBULB_FEATURES, carbon_row, wetbulb_row  # noqa: E402
from forecasting.trees import export, predict  # noqa: E402

T0 = datetime(2026, 8, 1)


def wetbulb_data(bias: bool, days=40, seed=1):
    rng = random.Random(seed)
    rows, y, persistence, provider, test = [], [], [], [], []
    for i in range(days * 24):
        t = T0 + timedelta(hours=i)
        truth = 24 + 3 * math.sin(2 * math.pi * (t.hour - 9) / 24) + rng.gauss(0, 0.3)
        afternoon = 12 <= t.hour <= 17
        prov = truth + (1.8 if (bias and afternoon) else 0.0) + rng.gauss(0, 0.3 if bias else 0.05)
        hour = t.strftime("%Y-%m-%dT%H:00")
        rows.append(wetbulb_row(hour, lead_h=i % 48, provider_t_wb=prov, provider_t_db=prov + 5,
                                provider_rh=70, recent_residual=0.0))
        y.append(truth)
        persistence.append(24 + 3 * math.sin(2 * math.pi * (t.hour - 9) / 24) + rng.gauss(0, 1.0))
        provider.append(prov)
        test.append(i >= (days - 7) * 24)
    return rows, y, persistence, provider, test


def test_model_beats_biased_provider_and_is_used():
    rows, y, pers, prov, test = wetbulb_data(bias=True)
    v, model = fit_and_judge("t_wb", "ap-south-1", rows, y, WETBULB_FEATURES, pers, prov, test)
    assert v.use_model, v
    assert v.mae_model < v.mae_provider < 1.0


def test_model_not_used_when_provider_is_already_best():
    rows, y, pers, prov, test = wetbulb_data(bias=False)
    v, _ = fit_and_judge("t_wb", "eu-north-1", rows, y, WETBULB_FEATURES, pers, prov, test)
    assert not v.use_model
    assert v.mae_provider < v.mae_model


def test_carbon_model_against_persistence():
    rng = random.Random(3)
    rows, y, pers, prov, test = [], [], [], [], []
    ci = [500 - 150 * max(0, math.cos(2 * math.pi * (h % 24 - 12) / 24)) + rng.gauss(0, 10) for h in range(24 * 40)]
    for i in range(24, len(ci) - 12):
        for lead in (6, 12):
            j = i + lead
            hour = (T0 + timedelta(hours=j)).strftime("%Y-%m-%dT%H:00")
            rows.append(carbon_row(hour, lead, last_ci=ci[i], same_hour_yesterday=ci[j - 24]))
            y.append(ci[j])
            pers.append(ci[i])
            prov.append(ci[i])          # no provider forecast: latest value held
            test.append(i >= 33 * 24)
    v, _ = fit_and_judge("ci", "ap-south-1", rows, y, CARBON_FEATURES, pers, prov, test)
    assert v.use_model and v.mae_model < 0.5 * v.mae_persistence


def test_exported_trees_match_sklearn():
    from sklearn.ensemble import GradientBoostingRegressor

    rng = random.Random(0)
    X = [[rng.uniform(-1, 1) for _ in range(3)] for _ in range(300)]
    y = [x[0] * 2 - x[1] ** 2 + 0.5 * (x[2] > 0) for x in X]
    m = GradientBoostingRegressor(n_estimators=40, max_depth=3, random_state=0).fit(X, y)
    exported = export(m, ["a", "b", "c"])
    ours = predict(exported, [{"a": x[0], "b": x[1], "c": x[2]} for x in X[:50]])
    assert ours == pytest.approx(list(m.predict(X[:50])), abs=1e-4)


def test_not_enough_data():
    with pytest.raises(ValueError):
        fit_and_judge("t_wb", "x", [], [], WETBULB_FEATURES, [], [], [])
