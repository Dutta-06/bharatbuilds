"""Export a fitted sklearn GradientBoostingRegressor to JSON and predict without sklearn."""

from __future__ import annotations


def export(model, feature_names: list[str]) -> dict:
    """Serialise a fitted sklearn.ensemble.GradientBoostingRegressor (loss='squared_error')."""
    trees = []
    for est in model.estimators_[:, 0]:
        t = est.tree_
        trees.append({
            "feature": t.feature.tolist(),
            "threshold": [round(float(x), 6) for x in t.threshold],
            "left": t.children_left.tolist(),
            "right": t.children_right.tolist(),
            "value": [round(float(v[0][0]), 6) for v in t.value],
        })
    init = model.init_
    base = float(init.constant_[0][0]) if hasattr(init, "constant_") else float(model._raw_predict_init([[0] * len(feature_names)])[0][0])
    return {"kind": "gbr", "features": feature_names, "learning_rate": float(model.learning_rate),
            "base": round(base, 6), "trees": trees}


def predict_one(model: dict, x: list[float]) -> float:
    total = model["base"]
    lr = model["learning_rate"]
    for t in model["trees"]:
        node = 0
        while t["left"][node] != -1:
            node = t["left"][node] if x[t["feature"][node]] <= t["threshold"][node] else t["right"][node]
        total += lr * t["value"][node]
    return total


def predict(model: dict, rows: list[dict]) -> list[float]:
    names = model["features"]
    return [predict_one(model, [float(r[n]) for n in names]) for r in rows]
