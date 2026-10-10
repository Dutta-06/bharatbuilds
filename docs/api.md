# Tidewise API

Base URL: the stack's `ApiUrl` output (CloudFront). JSON in, JSON out. CORS is open.
All hours are UTC, written `YYYY-MM-DDTHH:00`.

## Public: the water price of compute

`GET /price?region=ap-south-1&hour=2026-10-10T09:00&gpu=a100`

```json
{"region": "ap-south-1", "hour": "2026-10-10T09:00", "gpu": "a100",
 "per_kwh_it":   {"litres": 4.21, "litres_low": 2.4, "litres_high": 6.0, "kg_co2": 0.78, "litres_site": 2.22, "litres_grid": 1.99},
 "per_gpu_hour": {"litres": 1.53, "...": "..."},
 "inputs": {"t_wb": 27.4, "ci_g_per_kwh": 680, "ci_source": "electricitymaps-forecast", "weather_source": "open-meteo"}}
```

`hour` defaults to now and must fall in the next 48 h. Responses are cached for 5 minutes.
The route is throttled (50 requests/s, burst 100).

**API keys:** API Gateway HTTP APIs, which this uses for cost and latency, do not support
API keys or usage plans; REST APIs do. Throttling covers abuse for now. Per-consumer keys
would mean putting `/price` on a REST API.

## Jobs
| Method | Path | |
|---|---|---|
| `POST` | `/jobs` | Submit: `gpu_hours`, `deadline_h` or `deadline`, `submit_region`, optional `gpus`, `gpu`, `allowed_regions`, `data_residency`, `max_delay_h`, `weights {water, carbon}`, `team`, `splittable`, `max_chunks`, `name` |
| `GET` | `/jobs` | Queue, newest first (`?limit=`) |
| `GET` | `/jobs/{id}` | Job, placement, explanation, preview receipt, split plan |
| `GET` | `/jobs/{id}/receipt` | `200` final receipt once run, else `202` with the preview |

## Grid
| Method | Path | |
|---|---|---|
| `GET` | `/surface?gpu_hours=4&w_water=0.5&w_carbon=0.5&baseline=ap-south-1` | 48 h × regions cost grid |
| `GET` | `/regions` | Region metadata |

## Team policies (sign-in required)
`GET /policies/{team}` and `PUT /policies/{team}` with `Authorization: <Cognito ID token>`.
Anyone signed in can read. Only the `platform-leads` group can write.

```json
{"weights": {"water": 0.7, "carbon": 0.3}, "allowed_regions": ["ap-south-1", "eu-north-1"],
 "data_residency": false, "max_delay_h": 24}
```

A job with `"team": "<team>"` is placed under the policy. The team's weights replace the
job's. The job may narrow `allowed_regions` but never widen them.


## GET /savings?team=ml&days=30

Litres and kg CO2 saved by Tidewise placements over the last `days` (1-365, default 30): per day (with running
totals) and per team. `team` filters to one team; jobs submitted without a team count as `unassigned`.
Modelled figures: each job's chosen placement versus running it immediately in its submit region.

## POST /jobs/{id}/reschedule

Moves a job that is **waiting for its start** to a better window, if the newest forecast has one inside the
job's own constraints (allowed regions, residency, deadline, remaining `max_delay_h`). Returns
`{"rescheduled": true, "from": {...}, "to": {...}, "improvement": 0.31}` or `{"rescheduled": false, "reason": ...}`.
`409` if the job is not waiting (already running, done or failed); `502` if the old run could not be stopped, in
which case nothing is changed. The pipeline also emails (SNS) when a waiting job could improve by 15% or more,
once per new plan; nothing moves unless someone calls this (the dashboard button does).

## Power and facility operations

| Method | Route | Behavior |
|---|---|---|
| `GET` | `/facilities` | Public demo registry. |
| `GET` | `/facilities/{id}` | Facility state, impact metrics and associated Tidewise jobs. |
| `GET` | `/facilities/{id}/decisions` | Latest 30 persisted decision batches. |
| `POST` | `/facilities/{id}/simulate-power` | Cognito platform-leads only; IoT publish (202 pending), or demo reset (200). |

The site is a physical facility, never an AWS region. Power events affect only
explicitly associated jobs. POST accepts power_state (GRID, BATTERY_TRANSITION,
GENERATOR, GRID_RECOVERY), advance_s (1–86400), and optional event_id. operation:
reset provisions/reset the fixed demo only. Missing auth 401; wrong group 403;
invalid input 400; unknown/private facility 404; domain ordering/transition/write
conflicts 409. Publishing is asynchronous: inspect last_event_id and decisions
for confirmation. Public POST /jobs rejects facility metadata (403); trusted
IAM backend provisioning is required. Existing unassociated submissions are unchanged.

See [Power & Operations](dg-shift.md) for event schema, lifecycle,
security, simulator commands, model assumptions and recovery.

Submissions now return 409 when a job ID already exists, preventing public callers
from overwriting demo or other workload records. Execution confirmation is sent
only after the launch guard permits work; notification failure does not prevent
receipt finalization.
