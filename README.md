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
| 3 Local backend | Done: SAM template, single-table DynamoDB, 4 Lambdas, LocalStack, `make seed`; `curl localhost:3000/risk` verified |
| 4+ | Not started |

## Risk engine

Pure Python 3.12, standard library only.

```bash
pip install -r requirements-dev.txt
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

## Backend on a laptop

Needs Docker and the SAM CLI (`pip install aws-sam-cli`). No AWS account needed.

```bash
make local-up                   # LocalStack (DynamoDB, S3) in Docker
make local-setup                # table + bucket, upload city files
make seed                       # every cell from live Open-Meteo
make seed SEED_ARGS=--offline   # ...or from the synthetic fixture, shifted to today
make api                        # sam local start-api on :3000

curl "localhost:3000/risk?lat=28.7&lon=77.1&work=heavy"
curl "localhost:3000/risk?city=delhi&cell=rohini&work=light&lang=hi"
curl -X POST localhost:3000/subscribe -H 'content-type: application/json' \
  -d '{"city":"delhi","cell_id":"rohini","work":"heavy","contact":"you@example.com"}'
```

If `public.ecr.aws` is blocked on your network, run
`docker pull amazon/aws-lambda-python:3.12` and use
`make api SAM_LOCAL_ARGS="--invoke-image amazon/aws-lambda-python:3.12"`.

API, data model and access patterns: [`docs/data-model.md`](docs/data-model.md).

| Function | Trigger | Does |
|---|---|---|
| `fetch_forecast` | Step Functions (Step 4) | Open-Meteo call for one cell |
| `compute_risk` | Step Functions (Step 4) | Engine for one cell, writes 48 rows |
| `get_risk` | `GET /risk?lat&lon&work&lang` or `?city&cell` | Nearest cell, next 48 h, safe windows |
| `subscribe` | `POST /subscribe` | Stores cell, work, language, channel, contact |

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
backend/           AWS code shared by the Lambdas (DynamoDB keys, HTTP helpers)
functions/         one folder per Lambda handler
template.yaml      SAM template (table, bucket, layer, functions, HTTP API)
Makefile           build, LocalStack, seed, local API
docker-compose.yml LocalStack
tests/
```
