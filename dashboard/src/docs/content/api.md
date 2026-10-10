# API reference

Everything in the dashboard is available over a JSON HTTP API. Base URL: the `ApiUrl` output of your deployed stack. Requests and responses are JSON. CORS is open. All hours are UTC, written `YYYY-MM-DDTHH:00`.

## Conventions

- **Errors** are JSON: `{"error": "message"}` with a `4xx` or `5xx` status. `400` means the request was invalid and the message says which field.
- **Throttling:** 50 requests per second, burst 100, across the API.
- **Authentication:** only the policy routes need a sign-in. Send the Cognito ID token in the `Authorization` header.
- **Caching:** `/price` is cached for 5 minutes. Other routes are not cached.

## Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/regions` | Region metadata |
| `GET` | `/surface` | Cost for every region and hour over 48 hours |
| `GET` | `/price` | Water and carbon price of compute at one place and hour |
| `POST` | `/jobs` | Submit a job |
| `GET` | `/jobs` | List jobs, newest first |
| `GET` | `/jobs/{id}` | One job with placement and explanation |
| `GET` | `/jobs/{id}/receipt` | The receipt |
| `POST` | `/jobs/{id}/reschedule` | Move a waiting job to a better slot |
| `GET` | `/savings` | Cumulative savings |
| `POST` | `/chat` | Ask the assistant |
| `GET` | `/policies/{team}` | Read a team policy (sign-in) |
| `PUT` | `/policies/{team}` | Write a team policy (sign-in, `platform-leads` only) |

## Submit a job

`POST /jobs`

| Field | Type | Notes |
|---|---|---|
| `gpu_hours` | number | Required. 0.01 to 10000. |
| `deadline_h` or `deadline` | number or ISO UTC time | Required, one of them. `deadline_h` is hours from now, 0.1 to 720. |
| `submit_region` | string | Default `ap-south-1`. Must be a known region. |
| `gpus` | integer | 1 to 1024. Default 1. |
| `gpu` | string | `t4`, `l4`, `v100`, `a100` (default) or `h100`. |
| `allowed_regions` | list | Non-empty list of region ids. |
| `data_residency` | boolean | Keep the job in the geography of `submit_region`. |
| `max_delay_h` | number | 0 to 720. Longest wait before starting. |
| `weights` | object | `{"water": 0.5, "carbon": 0.5}`. |
| `team` | string | Applies the team's [policy](#/docs/guide-policies). |
| `splittable` | boolean | Also compute a split plan. |
| `max_chunks` | integer | 1 to 6. Default 2. Used with `splittable`. |
| `name` | string | Up to 80 characters. |

```bash
curl -X POST "$API/jobs" -H 'content-type: application/json' \
  -d '{"gpu_hours": 8, "deadline_h": 24, "submit_region": "ap-south-1",
       "weights": {"water": 0.7, "carbon": 0.3}, "name": "nightly eval"}'
```

The response is the job: `job_id`, `status`, `request`, `placement` (region, start, cost index, water and carbon), the plain-language explanation, and `alternatives`. A job that cannot meet your constraints returns `status: "infeasible"` and an explanation of what to change.

## List and read jobs

- `GET /jobs?limit=50` returns the newest jobs.
- `GET /jobs/{id}` returns one job with its placement, explanation, preview receipt and, for split jobs, the split plan.
- `GET /jobs/{id}/receipt` returns `200` with the final receipt once the job has run, otherwise `202` with the preview receipt.

## Cost surface

`GET /surface?gpu_hours=4&w_water=0.5&w_carbon=0.5&baseline=ap-south-1`

Returns the hourly cost grid for every region over the next 48 hours, with the forecast run time and the data source for each region. The Surface page is this response drawn as a heatmap.

## Price

`GET /price?region=ap-south-1&hour=2026-10-10T09:00&gpu=a100`

Returns litres of water and kg of CO₂ per kWh of IT energy and per GPU-hour, with a low and high range, the split between site cooling water and grid water, and the weather and carbon inputs used. `hour` defaults to now and must be within the next 48 hours.

## Reschedule

`POST /jobs/{id}/reschedule` moves a job that is still waiting to a better window, if the newest forecast has one inside the job's own constraints.

- `{"rescheduled": true, "from": {...}, "to": {...}, "improvement": 0.31}` when moved.
- `{"rescheduled": false, "reason": "..."}` when no better slot exists.
- `409` if the job is not waiting. `502` if the old run could not be stopped, in which case nothing changed.

## Savings

`GET /savings?team=ml&days=30` returns litres and kg of CO₂ saved per day, with running totals, and per team. `days` is 1 to 365, default 30. Jobs with no team count as `unassigned`.

## Assistant

`POST /chat` with `{"message": "..."}` (1 to 2000 characters) returns `{"reply": "...", "tool_calls": [...]}`. It answers within about 24 seconds. If it takes longer you get `504`, and if the language model is unavailable you get `503`. A `504` after you asked it to place a job may still have placed the job, so check the [Queue](#/docs/guide-queue) first.

## Team policies

`GET /policies/{team}` and `PUT /policies/{team}` with `Authorization: <Cognito ID token>`. Anyone signed in can read. Only the `platform-leads` group can write.

```json
{"weights": {"water": 0.7, "carbon": 0.3},
 "allowed_regions": ["ap-south-1", "eu-north-1"],
 "data_residency": false, "max_delay_h": 24}
```

`max_delay_h` is 0 to 720. A job submitted with `"team": "<team>"` uses the team's weights. It can narrow `allowed_regions` but never widen them.

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

See [Power & Operations](#/docs/power-operations) for event schema, lifecycle,
security, simulator commands, model assumptions and recovery.

Submissions now return 409 when a job ID already exists, preventing public callers
from overwriting demo or other workload records. Execution confirmation is sent
only after the launch guard permits work; notification failure does not prevent
receipt finalization.
