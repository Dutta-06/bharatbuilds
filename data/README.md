# Data

| Folder | One file per city | What it holds |
|---|---|---|
| `cities/` | `<city>.json` | Bounds, timezone, and the cells: id, name (English + Hindi), centroid, elevation |
| `hotspots/` | `<city>.json` | Known waterlogging spots, each with sources and the cell it falls in |
| `relief/` | `<city>.json` | Water, shade and shelter points for the map |
| `schemas/` | | JSON schemas the validator checks against |

A cell is a locality people name ("Rohini", "Okhla"). It is a centroid, not a
polygon: any point belongs to its nearest cell.

## Adding a city

1. Create `cities/<city>.json` (copy `delhi.json`). Pick 10-60 localities people
   actually say, at least 1 km apart, with centroids inside `bounds`.
2. Fill elevations once: `python scripts/fill_elevation.py <city>`.
3. Optionally add `hotspots/<city>.json` and `relief/<city>.json`, then run
   `python scripts/assign_cells.py <city>` to set each entry's `cell_id`.
4. `python scripts/validate_data.py` must say OK. `python scripts/render_map.py <city>`
   writes `docs/maps/<city>.html` so you can check that it looks right.

No code changes are needed.

## Before the demo

The Delhi files ship with `verified: false` on every hotspot and relief point:

* **Hotspots.** The names come from the reports listed in `sources`, but those
  pages could not be opened from the build environment, and the pins were
  placed by hand. Open each source, confirm the name, and drag the pin if needed.
* **Relief points.** The parks and gurudwaras are real places, but the pins are
  approximate. There are no piyaos yet. Add real ones from a site visit, since
  they are the most useful type.
* **Elevation.** It is empty until `fill_elevation.py` runs, because Open-Meteo
  was not reachable from the build environment.

`python scripts/validate_data.py --strict` fails until all of this is done.
