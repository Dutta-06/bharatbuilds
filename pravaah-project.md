# Pravaah — Water- and Carbon-Aware Scheduling for AI Workloads

Environmental Hacks (Bharat Builds Tour, event 02), Heat and Water track, Oct 8–11, 2026.

This document replaces the earlier Chhaanv scope and build plan in full.

---

## 1. One line

AI jobs are flexible in time and place. Pravaah runs them where cooling needs the least water and the grid is cleanest, without missing a deadline, and issues a receipt for what was saved.

## 2. Problem

Data centers reject heat mainly by evaporating water. Water per kWh rises steeply with outdoor wet-bulb temperature. Grid carbon intensity swings by hour. So the environmental cost of one GPU-hour differs several-fold between a hot afternoon in a water-stressed city and a cool night in a wet region. Schedulers today see none of this; they see a queue.

City angle (why this is Heat and Water): a data center in NCR evaporates water from the same stressed supply the surrounding colonies depend on, and its cooling demand peaks on exactly the afternoons the city's does.

## 3. Insight

Training, fine-tuning, batch inference and evaluation sweeps have deadlines in hours or days, not seconds. That slack is a free lever. Carbon-aware scheduling already uses it; nobody uses it for water. Pravaah optimizes both, jointly.

## 4. Scope

### Users

| User | Needs | Access |
|---|---|---|
| ML engineer (primary) | Submit a job with a deadline, get it run cheaply in water and carbon, see the receipt | API, CLI, dashboard |
| Platform / sustainability lead | Aggregate savings, forecast quality, policy weights per team | Dashboard, Cognito sign-in |
| Anyone | Query "the water price of compute" for a region and hour | Public read API |

### In scope (Core, must ship)

1. Cost model library: litres and kg CO₂ per GPU-hour per region per hour, every coefficient sourced.
2. Hourly forecast pipeline: wet-bulb and carbon intensity 48 h ahead for 5 to 8 AWS regions.
3. Scheduler: deadline-constrained placement over the (region, hour) grid.
4. Executor: Step Functions waits until the chosen hour and launches the job in the chosen region, measures it, writes a receipt.
5. Dashboard: queue, cost surface map, placements, cumulative savings, forecast error.
6. Receipt: per job, chosen slot versus "run now, here", measured energy.
7. Deployed on AWS, public URL, 3-minute video, Builder Center blog.

### Expand (ship if Core is stable)

8. Splittable jobs: integer program with OR-Tools across multiple windows.
9. Water-stress weighting from WRI Aqueduct per region.
10. Per-team policy weights and Cognito sign-in for the platform view.
11. Strands assistant: "when and where should I run this 20-GPU-hour job by Friday?"
12. Public "water price of compute" API with keys and docs.
13. Naive-versus-scheduled replay over a public cluster trace, as the headline chart.
14. Kubernetes scheduler plugin prototype (design plus a stub).

### Design only (slide in the video)

- Demand-response pause during grid stress.
- Provider-reported WUE ingestion where disclosed.
- Facility-level simulation with OpenDC.

### Out of scope

- Controlling any real facility's cooling or power.
- Plant-level energy-embedded water; grid averages only.
- Real-time (sub-hour) rescheduling.
- Any workload that is not deadline-flexible.

### Definition of done

A stranger with the URL submits a 1-GPU-hour job with a 24-hour deadline, watches the scheduler pick a region and hour, sees the job actually run there, and receives a receipt with measured energy and modelled litres and kg saved, with nobody on the team touching anything.

## 5. Cost model (the core file)

Per region `r`, hour `h`:

- `T_wb(r,h)` wet-bulb temperature from Open-Meteo forecast (temperature, RH, pressure) via Stull (2011).
- `WUE_site(r,h)` on-site cooling water, L/kWh, a function of wet-bulb and cooling type, from published WUE curves. Separate curves for evaporative, hybrid, and air-cooled; default by region from public disclosures where available, otherwise hybrid.
- `WUE_grid(r)` water embedded in electricity generation, L/kWh, from grid mix (coal, gas, hydro, solar, wind) using published per-source water factors.
- `CI(r,h)` carbon intensity, gCO₂/kWh, from Electricity Maps by zone.
- `E_job` energy per GPU-hour from declared hardware; replaced by measured kWh (Kepler / CodeCarbon) after the run.
- `S(r)` water-stress multiplier from WRI Aqueduct baseline water stress for the region's basin.

```
litres(r,h)  = E_job × (WUE_site(r,h) + WUE_grid(r))
kg(r,h)      = E_job × CI(r,h) / 1000
cost(r,h)    = w_water × litres(r,h) × S(r) + w_carbon × kg(r,h)
```

Weights `w_water`, `w_carbon` set by the submitter or team policy. Every coefficient lives in `model/coefficients.yaml` with a source URL and a note on uncertainty. The relative ranking of slots is what the scheduler uses; absolute litres are reported with an uncertainty band.

## 6. Architecture

```
Job submit (API Gateway + Lambda)
        │
        ▼
Step Functions: schedule-and-run
  1. load 48h forecasts (DynamoDB)      ◄── hourly forecast pipeline
  2. score (region × hour) grid              EventBridge → Step Functions
  3. optimize under deadline                   Open-Meteo wet-bulb
  4. Wait until chosen hour                    Electricity Maps carbon
  5. launch in chosen region                   SageMaker 48h forecasts
     (ECS Fargate task or Lambda)              → DynamoDB
  6. measure (Kepler / CodeCarbon)
  7. write receipt (DynamoDB + S3)
        │
        ▼
Dashboard (Amplify + CloudFront) · SNS notifications · Strands assistant
```

## 7. AWS and open-source footprint

| Piece | Role |
|---|---|
| Lambda, API Gateway | Submit, query, receipt endpoints |
| Step Functions | Forecast pipeline; schedule-and-run with a Wait state |
| EventBridge | Hourly forecast trigger |
| DynamoDB | Forecasts, jobs, receipts, policies |
| S3 | Raw forecast pulls, receipts archive, trace data |
| ECS Fargate | Runs the actual job in the chosen region (tiny task) |
| SageMaker | Train and serve the two forecast models |
| SNS | Job placed / started / finished notifications |
| CloudFront, Amplify Hosting | Dashboard |
| CloudWatch | Pipeline health, forecast error metrics |
| Cognito | Platform-lead sign-in, public API keys |
| SAM CLI, LocalStack (open source) | Local build before any spend |
| Strands Agents SDK (open source) | Scheduling assistant |
| Kepler / CodeCarbon (open source) | Measured energy per job |
| OR-Tools (open source) | Integer program for splittable jobs |
| Carbon Aware SDK, carbon-aware KEDA scaler (open source) | Cited prior art; the gap we extend |

Not used: EC2, Lightsail, App Runner, EKS (design only for the plugin), OpenSearch.

---

## 8. Build plan

Ordered by dependency, not by day. Each step has a goal, tasks, and a "done when" check. Do not start a step until its dependencies are done.

### Step 0 — Setup and eligibility (Core)

- [ ] Every member verifies student status on AWS Builder Center.
- [ ] Team leader checks in on the hackathon page; Luma application if attending DTU.
- [ ] One team AWS account, MFA on root, IAM users per member, billing alarms at $5 and $20.
- [ ] Repo `pravaah/` with branch protection; Python 3.12, Node 20, AWS CLI, SAM CLI, Docker.
- [ ] Register for an Electricity Maps free API key; confirm which zones map to the chosen AWS regions.
- [ ] Shared doc for the video script and blog outline.

**Done when:** `sam build` passes on an empty template for every member and the Electricity Maps key returns data for one zone.

### Step 1 — Cost model library (Core)

- [ ] `model/wetbulb.py`: Stull wet-bulb from T, RH, P, with tests against published values.
- [ ] `model/coefficients.yaml`: WUE curves by cooling type, grid water factors by source, water-stress by region, each with a source URL and uncertainty note.
- [ ] `model/water.py`: `WUE_site(T_wb, cooling_type)`, `WUE_grid(mix)`.
- [ ] `model/cost.py`: `cost(r, h, E_job, weights)` and `receipt(chosen, baseline)`.
- [ ] Validation notebook: reproduce at least two published WUE figures within a stated tolerance.
- [ ] CLI: `python -m model --region ap-south-1 --hour 2026-10-10T15:00 --gpu-hours 4` prints litres and kg.

**Done when:** tests pass and one person who did not write it can explain where every number comes from.

### Step 2 — Region and data configuration (Core)

- [ ] `data/regions.yaml`: 5 to 8 AWS regions with lat/lon, Electricity Maps zone, default cooling type, Aqueduct stress score, and sources.
- [ ] Pull 30 to 60 days of history: Open-Meteo archive (T, RH, P) and Electricity Maps history per zone, stored to S3 as Parquet.
- [ ] Public cluster trace (Google or Alibaba) sampled to a realistic job queue: GPU-hours, submit times, deadlines. Stored as `data/trace.csv`.
- [ ] Schema validation script for all config.

**Done when:** `python scripts/validate_data.py` passes and the history covers every region in the config.

### Step 3 — Local infrastructure with SAM and LocalStack (Core)

- [ ] SAM template: DynamoDB single table, S3 bucket, HTTP API, Lambdas below.
- [ ] DynamoDB keys: `PK=FORECAST#<region>`, `SK=HOUR#<iso>`; `PK=JOB#<id>`; `PK=RECEIPT#<job>`; `PK=POLICY#<team>`. Write access patterns down first.
- [ ] Lambda `fetch_forecast`: Open-Meteo plus Electricity Maps for one region, raw to S3.
- [ ] Lambda `score_grid`: cost model over (region, hour), returns the surface.
- [ ] Lambda `submit_job`, `get_job`, `get_receipt`, `get_surface`.
- [ ] LocalStack config; `sam local start-api`; `make seed` runs the pipeline for all regions locally.

**Done when:** `curl localhost:3000/surface?gpu_hours=4` returns a plausible 48-hour cost grid from local data.

### Step 4 — Forecast models (Core)

- [ ] Wet-bulb 48 h model: gradient boosting on numerical forecast plus recent residuals, per region.
- [ ] Carbon-intensity 48 h model: same, with hour-of-day, day-of-week, solar features.
- [ ] Baseline: persistence and the raw provider forecast; the model must beat both on held-out days or it is not used.
- [ ] Train in a notebook first; then as a SageMaker training job; serve from a SageMaker endpoint or export to a Lambda if the endpoint cost is a concern.
- [ ] Forecast error written to DynamoDB per region per run.

**Done when:** held-out MAE beats persistence for every region and the dashboard can show the number.

### Step 5 — Hourly forecast pipeline with Step Functions (Core)

- [ ] State machine `pravaah-forecast`: Map over regions → `fetch_forecast` → predict → write 48 rows per region to DynamoDB → log error metrics.
- [ ] EventBridge hourly trigger; manual run for demos.
- [ ] Retries and a catch-all failure state to CloudWatch Logs.

**Done when:** the table has 48 rows per region after a run and a CloudWatch metric shows the run.

### Step 6 — Scheduler (Core)

- [ ] `scheduler/greedy.py`: pick the min-cost (region, hour) with `hour + duration ≤ deadline`.
- [ ] Constraints: allowed regions, data-residency flag, max delay.
- [ ] Explanation output: why this slot, the top three alternatives, cost of running now.
- [ ] Unit tests with synthetic surfaces, including "no feasible slot" and "deadline now".

**Done when:** every job in the trace gets a feasible slot or a clear infeasibility reason.

### Step 7 — Executor (Core)

- [ ] State machine `pravaah-run`: load job → score → schedule → `Wait` until chosen hour → launch ECS Fargate task in chosen region (a small PyTorch training script with CodeCarbon enabled) → collect energy → compute receipt → notify.
- [ ] Cross-region launch via a Lambda that assumes a role in the target region.
- [ ] Kepler on the task where feasible; CodeCarbon as the always-on fallback.
- [ ] Receipt to DynamoDB and S3: chosen slot, baseline slot, modelled litres and kg, measured kWh, uncertainty band.
- [ ] SNS notifications: placed, started, finished.

**Done when:** a submitted job runs in a different region than it was submitted from and the receipt shows measured kWh.

### Step 8 — Deploy to AWS (Core)

- [ ] `sam deploy` to the team account; run the forecast pipeline once.
- [ ] HTTP API behind CloudFront with short caching on read endpoints.
- [ ] CloudWatch dashboard: pipeline runs, forecast error, jobs placed, savings.
- [ ] Confirm cost explorer shows free-tier use.

**Done when:** the submit-and-run loop works from a phone on mobile data.

### Step 9 — Dashboard (Core)

- [ ] React + Vite on Amplify. Pages: Submit, Queue, Surface (map of regions coloured by cost for a selected hour, with a time scrubber), Job detail with receipt, Savings (cumulative litres and kg, naive versus scheduled), Forecast quality.
- [ ] Leaflet with OpenStreetMap tiles for the map.
- [ ] Mobile-friendly; Lighthouse above 80.

**Done when:** a stranger can submit a job, find it in the queue, and read its receipt without help.

### Step 10 — Trace replay and headline chart (Expand)

- [ ] Replay the sampled cluster trace through the scheduler offline: naive (submit region, submit time) versus Pravaah.
- [ ] Output: total litres, kg, deadline hit rate, median delay. Two bars for the video.
- [ ] Sensitivity: how savings change with deadline slack and with weights.

**Done when:** the Savings page shows the replay result with the assumptions listed beside it.

### Step 11 — Splittable jobs and water stress (Expand)

- [ ] OR-Tools integer program: split a job across windows and regions with a max-split constraint.
- [ ] Aqueduct water-stress multiplier wired into the cost and shown on the surface map.

**Done when:** a 20-GPU-hour job can be split across two slots and the receipt explains both.

### Step 12 — Policy, auth, public API (Expand)

- [ ] Cognito for platform leads; per-team weights and allowed regions as a policy document.
- [ ] Public read endpoint `GET /price?region&hour` with API keys and a one-page docs site.

**Done when:** a platform lead can change a team's weights and the next job reflects them.

### Step 13 — Assistant (Expand)

- [ ] Strands agent with tools `get_surface`, `submit_job`, `get_receipt`.
- [ ] 20-question test set; must pass 16.

**Done when:** "run this 8-GPU-hour job by Friday with least water" submits a correctly constrained job.

### Step 14 — Hardening (Core)

- [ ] Error states in the dashboard; alarms on pipeline failure; load test read endpoints.
- [ ] Freeze features. README with architecture, how to run locally, how to deploy, how to add a region.

**Done when:** the definition-of-done loop passes three times in a row.

### Step 15 — Demo video (Core)

- [ ] Script, three minutes:
  - 0:00–0:30 Problem: wet-bulb versus water-per-kWh curve; a Delhi afternoon versus a coastal night; the colony and the data center drawing on the same supply.
  - 0:30–1:30 Submit a 4-GPU-hour job with a Friday deadline. The surface map over 48 hours. The scheduler picks a slot and explains why.
  - 1:30–2:15 Step Functions console: the Wait, the launch in another region, the measured kWh coming back. The receipt.
  - 2:15–2:45 Savings page: trace replay, naive versus scheduled. Forecast quality panel.
  - 2:45–3:00 Limitations in one line; "we used AI to decide when AI should run."
- [ ] Record screen and console separately; cut on a timeline; rehearse twice.

**Done when:** under 3:00 and every claim in it runs.

### Step 16 — Blog and submission (Core)

- [ ] Builder Center blog: the cost model and its sources, why water and carbon optima differ, what fought back (zone mapping, cross-region launch permissions, forecast models that didn't beat persistence at first).
- [ ] Submission: repo, URL, video, blog, track = Heat and Water, services used.

**Done when:** the submission confirmation is in the team leader's inbox.

---

## 9. Dependency map

```
0 → 1 → 3 → 5 → 6 → 7 → 8 → 9 → 14 → 15 → 16
      ↘ 2 ↗  ↘ 4 ↗           ↘ 10
                              ↘ 11
                              ↘ 12
                              ↘ 13
```

Steps 10–13 can run in parallel after Step 9, one person each. Anything in 10–13 not working when Step 14 begins becomes a "designed, not built" slide.

## 10. Limitations to state in every artefact

- No facility's cooling or power is controlled; cooling water is modelled from published curves.
- Energy-embedded water uses grid averages, not plant-level data.
- Provider WUE disclosure is inconsistent; absolute litres carry uncertainty, relative slot ranking is robust to it.
- Only deadline-flexible workloads benefit.

## 11. Metrics reported

Litres saved, kg CO₂ saved, deadline hit rate (target 100%), median delay introduced, forecast MAE per region, measured versus declared energy.
