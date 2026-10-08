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
| 5 Forecast pipeline | `pravaah-forecast` state machine, hourly schedule, verified in Step Functions Local |
| 7 Executor | `pravaah-run` state machine (Wait, cross-region worker, receipt, SNS), verified in Step Functions Local |
| 9 Dashboard | React + Vite + Leaflet: Submit, Queue, Surface, Job/receipt, Savings, Forecast quality |
| 10 Trace replay | `scripts/replay.py`: naive vs Pravaah, deadline hit rate, median delay, when-vs-where, slack and weight sensitivity; shown on the Savings page with its assumptions |
| 4 Forecast models | Gradient-boosted wet-bulb and carbon models judged against persistence and the provider; exported to JSON for Lambda; `predict` step in the pipeline; per-run forecast error. Training needs real history |
| 8 Deploy infra | In the template: CloudFront (5 min cache on reads), CloudWatch dashboard, 3 alarms → SNS. Deploying needs the AWS account (HUMAN-TODO) |
| 14 Hardening | Dashboard error states, alarms, `scripts/load_test.py`, docs below. Feature freeze and the three-in-a-row check are on the team |
| 11 Splittable jobs | OR-Tools CP-SAT plan (exact DP fallback in Lambda, tested to agree); `"splittable": true` on POST /jobs; shown on the job page. Executing split plans is design-only. Aqueduct stress multiplier is wired in, but scores still need looking up |
| 15-16 Video, blog | Drafts in `docs/` with [placeholders] for real numbers |
| 12 Policies, auth, public API | Cognito (platform-leads group) + JWT authorizer; GET/PUT /policies/{team} applied on submit; public throttled `GET /price`; [`docs/api.md`](docs/api.md); Policies page (untested without a user pool) |
| 17 Receipts, savings, nudges | Shareable/printable receipt page (JSON, CSV, print), `GET /savings` with a cumulative chart and per-team table, a nudge email when a much better slot opens for a waiting job and `POST /jobs/{id}/reschedule` to take it, `collect_history` Lambda saving real carbon history to S3, `scripts/set_water_stress.py` |
| 13 Assistant | Strands agent (Claude Opus 5.5 via Anthropic API or Bedrock) with get_surface / submit_job / get_receipt over the API; POST /chat; Assistant page; 20-case test set + grader (`make assistant-eval`, needs a model key) |

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
python scripts/replay.py                  # trace replay -> dashboard/public/replay.json
python scripts/train_forecasts.py         # Step 4 models (needs internet + history)
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

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the diagram.
Hourly pipeline: Open-Meteo + Electricity Maps → `pravaah-forecast` → DynamoDB.
Jobs: `POST /jobs` → scheduler → `pravaah-run` (Wait → run in the chosen region →
receipt → SNS). Dashboard on Amplify, API behind CloudFront.

## Deploy

```bash
aws configure                 # IAM user, region ap-south-1
make deploy                   # guided: stack name pravaah, ElectricityMapsToken, NotificationEmail
make deploy-workers           # the worker in all 8 regions (jobs really run where chosen)
make forecast-now             # first forecast run
python scripts/load_test.py "$(aws cloudformation describe-stacks --stack-name pravaah \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)/surface?gpu_hours=4"
```

## Add a region

1. Add it to `data/regions.yaml`: id, name, `geo`, lat/lon, `cooling_type`,
   `electricity_maps_zone`, `grid_mix`, `typical_ci_g_per_kwh`, `water_stress_score`.
   If AWS discloses its WUE, also add the figure under `regional_wue` in
   `model/coefficients.yaml`.
2. Add the id to `RegionList` in `template.yaml` and `WORKER_REGIONS` in the `Makefile`.
3. `python scripts/validate_data.py`, `python scripts/calibrate_wue.py <id>`, `make deploy deploy-workers`.

## Dashboard

```bash
make api            # in one terminal (backend on :3000)
make dashboard-dev  # in another: http://localhost:5173
```

Hosted on Amplify (`amplify.yml`). Set `VITE_API_URL` to the stack's `ApiUrl`.

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
forecasting/          Step 4 features, training/judging, JSON tree export, serving
assistant/            Step 13 Strands agent, tools, eval runner (evals/assistant.yaml)
statemachines/        pravaah-forecast and pravaah-run (ASL)
dashboard/            React + Vite + Leaflet front end
data/regions.yaml     candidate AWS regions
data/trace.synthetic.csv  labelled synthetic job queue (until the Alibaba trace is sampled)
scripts/              validate_data, calibrate_wue, pull_history, sample_trace, local_setup, seed_local
notebooks/            wue_validation (percent-format notebook)
docs/cost-model.md    one-page explainer
```
