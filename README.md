# Chhaanv

Heat and waterlogging risk, hour by hour, for the people who work outdoors in
Indian cities. Built for Environmental Hacks (Bharat Builds Tour), Heat and Water track.

The build plan is in [`chhaanv-build-plan.md`](chhaanv-build-plan.md), and
[`docs/thresholds.md`](docs/thresholds.md) explains how risk is decided.

## Status

| Step | State |
|---|---|
| 0 Setup | Repo, CI and SAM skeleton done. AWS account, IAM and eligibility are on the team |
| 1 Risk engine | Done: WBGT, heat index, ISO 7243 bands, waterlogging, EN/HI windows, CLI, tests |
| 2 City grid and data | Done except elevation (needs one run of `scripts/fill_elevation.py`) and checking hotspot/relief entries |
| 3+ | Not started |

## Risk engine

Pure Python 3.12, standard library only.

```bash
pip install pytest jsonschema
python -m pytest
python scripts/validate_data.py

# live forecast from Open-Meteo
python -m engine --lat 28.7 --lon 77.1 --work heavy
python -m engine --lat 28.7 --lon 77.1 --work heavy --lang hi

# by locality name (also marks hotspot cells)
python -m engine --city delhi --cell rohini --work heavy

# offline, using the synthetic Delhi fixture
python -m engine --from-file tests/engine/fixtures/delhi_may_synthetic.json --now 2026-05-26T05:00
```

Options: `--work light|moderate|heavy`, `--lang en|hi`, `--hazard heat|waterlogging|all`,
`--city`, `--cell`, `--hotspot`, `--unacclimatised`, `--json`.

## Data

Cities, waterlogging hotspots and relief points are JSON files in `data/`. See
[`data/README.md`](data/README.md) for how to add a city.

## Layout

```
engine/            risk engine (no AWS)
  wbgt.py          WBGT estimate (Stull wet bulb + globe heat balance; BoM cross-check)
  heat_index.py    NOAA heat index fallback
  thresholds.py    ISO 7243 bands per work intensity
  waterlogging.py  rain per 3 h x hotspot x elevation
  windows.py       plain-language safe windows
  strings/         all user-facing text (en, hi)
  openmeteo.py     forecast client
  risk.py          combines the above into 48-hour strips
  grid.py          city files, nearest-cell lookup
data/              cities, hotspots, relief points, JSON schemas
scripts/           validate_data, assign_cells, fill_elevation, render_map
functions/         Lambda handlers (Step 3+)
template.yaml      SAM template
tests/
```
