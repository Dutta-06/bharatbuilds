"""Region configuration from data/regions.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from . import coefficients as c

PATH = Path(__file__).resolve().parent.parent / "data" / "regions.yaml"


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    geo: str
    lat: float
    lon: float
    cooling_type: str
    electricity_maps_zone: str | None
    pue: float
    disclosed_wue: float | None
    wue_scale: float              # calibration factor; 1.0 until calibrated from weather history
    water_stress_score: float | None
    grid_mix: dict = field(default_factory=dict)
    typical_ci_g_per_kwh: float | None = None

    @property
    def stress_multiplier(self) -> float:
        if self.water_stress_score is None:
            return 1.0
        return 1.0 + self.water_stress_score / c.value("water_stress", "max_score")

    @property
    def calibrated(self) -> bool:
        return self.wue_scale != 1.0 or self.cooling_type == "air"


@lru_cache(maxsize=1)
def load(path: Path = PATH) -> dict[str, Region]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    disclosed = c.load()["regional_wue"]["values"]
    default_pue = c.value("pue", "default")
    out = {}
    for r in raw["regions"]:
        wue_key = r.get("disclosed_wue_key", r["id"])
        out[r["id"]] = Region(
            id=r["id"],
            name=r["name"],
            geo=r["geo"],
            lat=r["lat"],
            lon=r["lon"],
            cooling_type=r["cooling_type"],
            electricity_maps_zone=r.get("electricity_maps_zone"),
            pue=r.get("pue") or default_pue,
            disclosed_wue=disclosed.get(wue_key),
            wue_scale=r.get("wue_scale") or 1.0,
            water_stress_score=r.get("water_stress_score"),
            grid_mix=r.get("grid_mix", {}).get("shares", {}),
            typical_ci_g_per_kwh=r.get("typical_ci_g_per_kwh"),
        )
    return out


def get(region_id: str) -> Region:
    regions = load()
    try:
        return regions[region_id]
    except KeyError:
        raise ValueError(f"unknown region {region_id!r}; known: {', '.join(regions)}") from None
