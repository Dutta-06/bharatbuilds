"""Set cell_id on every hotspot and relief point to its nearest grid cell.

    python scripts/assign_cells.py            # all cities
    python scripts/assign_cells.py delhi
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _jsonio import dump, load  # noqa: E402
from engine.grid import DATA_DIR, city_ids, load_city  # noqa: E402

LAYERS = {"hotspots": "hotspots", "relief": "points"}


def assign(city_id: str) -> None:
    city = load_city(city_id)
    for folder, key in LAYERS.items():
        path = DATA_DIR / folder / f"{city_id}.json"
        if not path.exists():
            continue
        data = load(path)
        for item in data[key]:
            cell, km = city.nearest(item["lat"], item["lon"])
            item["cell_id"] = cell.id
            print(f"{folder}/{city_id}: {item['id']:28} -> {cell.id:18} {km:4.1f} km")
        dump(data, path)


if __name__ == "__main__":
    for cid in sys.argv[1:] or city_ids():
        assign(cid)
