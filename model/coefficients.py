"""Load model/coefficients.yaml. Every number the model uses comes through here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("coefficients.yaml")


@lru_cache(maxsize=1)
def load() -> dict:
    with PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def value(*path: str) -> float:
    """value("site_cooling", "tower", "cycles_of_concentration") -> 5"""
    node = load()
    for key in path:
        node = node[key]
    return node["value"] if isinstance(node, dict) and "value" in node else node


def uncertainty(*path: str) -> float:
    node = load()
    for key in path:
        node = node[key]
    return float(node.get("uncertainty", 0.0))
