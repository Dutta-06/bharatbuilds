# Pravaah

Water- and carbon-aware scheduling for AI workloads. AI jobs are flexible in
time and place. Pravaah runs them where cooling needs the least water and the
grid is cleanest, without missing a deadline, and issues a receipt for what was
saved.

Environmental Hacks (Bharat Builds Tour), Heat and Water track. Plan:
[`pravaah-project.md`](pravaah-project.md). How a GPU-hour is priced:
[`docs/cost-model.md`](docs/cost-model.md).

## Status

| Step | State |
|---|---|
| 0 Setup | Repo and CI. AWS account, Electricity Maps key and eligibility are on the team |
| 1 Cost model | Library, coefficients with sources, CLI, tests, validation notebook. Sources still need a human check (`checked: false`), and the validation notebook needs a run with internet access |
| 2 Data | Sources (Open-Meteo, Electricity Maps + labelled modelled fallback), history pull, trace sampler + synthetic trace. Pulls need internet (see HUMAN-TODO.md) |
| 3 Local backend | SAM, DynamoDB, 7 Lambdas, LocalStack, `make seed`; `curl localhost:3000/surface?gpu_hours=4` verified end to end |
| 6 Scheduler | Greedy, deadline-constrained, with constraints, alternatives and explanations |
| 4, 5, 7+ | Not started |

Anything that needs a human (keys, AWS, internet-only runs, source checks) is in
[`HUMAN-TODO.md`](HUMAN-TODO.md).

## Cost model

```bash
pip install -r requirements-dev.txt
make ci                                   # tests, config validation, CLI smoke test

# live weather from Open-Meteo (hours are UTC)
python -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4
python -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --compare

# offline
python -m model --region eu-north-1 --hour 2026-10-10T02:00 --gpu-hours 4 --temp 8 --rh 85 --ci 35

python scripts/calibrate_wue.py           # scale site-WUE curves to AWS disclosures (needs internet)
python notebooks/wue_validation.py        # uncalibrated curves vs published WUE (needs internet)
```

## Backend on a laptop

Needs Docker and the SAM CLI (`pip install aws-sam-cli`). No AWS account needed.

```bash
make local-up                   # LocalStack in Docker
make local-setup                # table + bucket
make seed                       # forecasts for every region (live Open-Meteo)
make seed SEED_ARGS=--offline   # ...or synthetic weather + modelled carbon, no internet
make api                        # sam local start-api on :3000

curl "localhost:3000/surface?gpu_hours=4"
curl -X POST localhost:3000/jobs -H 'content-type: application/json' \
  -d '{"gpu_hours": 4, "deadline_h": 24, "submit_region": "ap-south-1"}'
curl localhost:3000/jobs
```

If `public.ecr.aws` is blocked: `docker pull amazon/aws-lambda-python:3.12` and
`make api SAM_LOCAL_ARGS="--invoke-image amazon/aws-lambda-python:3.12"`.
Data model: [`docs/data-model.md`](docs/data-model.md).

## Layout

```
model/
  coefficients.yaml   every number, with source, uncertainty and a checked flag
  wetbulb.py          psychrometric wet-bulb (pressure-aware); Stull cross-check
  water.py            on-site WUE curves by cooling type, calibration, grid water
  energy.py           job energy from GPU type and hours
  cost.py             footprint, cost, receipt (with uncertainty bands)
  regions.py          loads data/regions.yaml
scheduler/            cost surface, greedy placement, trace loader
sources/              Open-Meteo, Electricity Maps, modelled carbon fallback, synthetic weather
backend/              DynamoDB access, forecasts store, jobs, HTTP helpers
functions/            one folder per Lambda
data/regions.yaml     candidate AWS regions
data/trace.synthetic.csv  labelled synthetic job queue (until the Alibaba trace is sampled)
scripts/              validate_data, calibrate_wue, pull_history, sample_trace, local_setup, seed_local
notebooks/            wue_validation (percent-format notebook)
docs/cost-model.md    one-page explainer
```
