"""Train and judge one model against its baselines on held-out days.

The rule from the plan: a model is only used if its held-out MAE beats BOTH
persistence and the raw provider forecast (for carbon, where the free tier has
no provider forecast, the provider baseline is "latest value held").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Verdict:
    target: str
    region: str
    n_train: int
    n_test: int
    mae_model: float
    mae_persistence: float
    mae_provider: float
    use_model: bool

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def mae(a, b) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


def fit_and_judge(target: str, region: str, rows: list[dict], y: list[float], features: list[str],
                  persistence: list[float], provider: list[float], test_mask: list[bool], seed: int = 0):
    """Returns (Verdict, exported model dict or None)."""
    from sklearn.ensemble import GradientBoostingRegressor

    from .trees import export, predict

    train = [i for i, t in enumerate(test_mask) if not t]
    test = [i for i, t in enumerate(test_mask) if t]
    if len(train) < 48 or len(test) < 24:
        raise ValueError(f"{region}/{target}: not enough data (train {len(train)}, test {len(test)})")
    X = [[r[f] for f in features] for r in rows]
    model = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
                                      random_state=seed)
    model.fit([X[i] for i in train], [y[i] for i in train])
    exported = export(model, features)
    pred = predict(exported, [rows[i] for i in test])
    yt = [y[i] for i in test]
    v = Verdict(target, region, len(train), len(test), mae(pred, yt),
                mae([persistence[i] for i in test], yt), mae([provider[i] for i in test], yt), False)
    v.use_model = v.mae_model < v.mae_persistence and v.mae_model < v.mae_provider
    return v, exported
