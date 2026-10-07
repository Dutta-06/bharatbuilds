"""City grids: load a city file and find the cell for a point.

A cell is a named locality with a centroid. Cells have no drawn boundary; a
point belongs to the nearest centroid (a Voronoi partition), which is how
people think about it too: "I'm near Okhla".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Cell:
    id: str
    name: str
    name_hi: str
    lat: float
    lon: float
    elevation_m: float | None


@dataclass(frozen=True)
class City:
    id: str
    name: str
    timezone: str
    bounds: dict
    ref_elevation_m: float | None
    cells: tuple[Cell, ...]

    def cell(self, cell_id: str) -> Cell:
        for c in self.cells:
            if c.id == cell_id:
                return c
        raise KeyError(cell_id)

    def contains(self, lat: float, lon: float) -> bool:
        b = self.bounds
        return b["south"] <= lat <= b["north"] and b["west"] <= lon <= b["east"]

    def nearest(self, lat: float, lon: float) -> tuple[Cell, float]:
        """(nearest cell, distance in km)."""
        return min(((c, haversine_km(lat, lon, c.lat, c.lon)) for c in self.cells),
                   key=lambda pair: pair[1])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def load_city(city_id: str, data_dir: Path = DATA_DIR) -> City:
    raw = json.loads((data_dir / "cities" / f"{city_id}.json").read_text(encoding="utf-8"))
    return City(
        id=raw["id"],
        name=raw["name"],
        timezone=raw["timezone"],
        bounds=raw["bounds"],
        ref_elevation_m=raw.get("ref_elevation_m"),
        cells=tuple(
            Cell(c["id"], c["name"], c["name_hi"], c["lat"], c["lon"], c.get("elevation_m"))
            for c in raw["cells"]
        ),
    )


def city_ids(data_dir: Path = DATA_DIR) -> list[str]:
    return sorted(p.stem for p in (data_dir / "cities").glob("*.json"))


def hotspot_cells(city_id: str, data_dir: Path = DATA_DIR) -> set[str]:
    """Ids of cells that contain at least one waterlogging hotspot."""
    path = data_dir / "hotspots" / f"{city_id}.json"
    if not path.exists():
        return set()
    hotspots = json.loads(path.read_text(encoding="utf-8"))["hotspots"]
    return {h["cell_id"] for h in hotspots if h.get("cell_id")}
