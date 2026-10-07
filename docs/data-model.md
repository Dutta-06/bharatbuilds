# DynamoDB data model

One table, `pravaah-main`: primary key (`PK`, `SK`), one global secondary index
(`GSI1PK`, `GSI1SK`), and TTL on `expires_at`. Capacity is provisioned inside
the always-free tier (table 15/20 + GSI 5/5 RCU/WCU).

## Access patterns

| # | Who | Pattern | Key condition |
|---|---|---|---|
| 1 | `store_forecast` | Write 48 forecast hours for a region | `PK = FORECAST#<region>`, `SK = HOUR#<UTC hour>` (batch) |
| 2 | `get_surface`, `score_grid` | Read the next 48 h for every region | per region: `PK = FORECAST#<region>`, `SK BETWEEN HOUR#<now> AND HOUR#<now+47h>` |
| 3 | pipeline, dashboard | Latest run per region | `PK = FORECAST#<region>`, `SK = META#latest` |
| 4 | `submit_job` / `score_grid` | Save a job and its placement | `PK = JOB#<id>`, `SK = META` |
| 5 | `get_job` | One job | `PK = JOB#<id>`, `SK = META` |
| 6 | `get_job` (queue) | Recent jobs, newest first | GSI1: `GSI1PK = JOBS`, sort `GSI1SK = <submitted_at>#<id>` descending |
| 7 | executor (Step 7) / `get_receipt` | Final receipt | `PK = RECEIPT#<job>`, `SK = META` |
| 8 | Step 12 | Team policy (weights, allowed regions) | `PK = POLICY#<team>`, `SK = META` (reserved) |

Pattern 6 puts every job in one GSI partition. That is fine at hackathon scale
(well under 1,000 writes/s). A real deployment would shard by day.

## Items

**Forecast hour** (one per region per UTC hour; raw inputs, not costs):

```json
{"PK": "FORECAST#ap-south-1", "SK": "HOUR#2026-10-10T09:00",
 "region": "ap-south-1", "hour": "2026-10-10T09:00",
 "t_db": 32.4, "rh": 71, "p_hpa": 1008.0, "t_wb": 27.6,
 "ci_g_per_kwh": 652, "ci_source": "electricitymaps-forecast",
 "mix": {"coal": 0.71, "solar": 0.09, "...": 0.2}, "weather_source": "open-meteo",
 "run_id": "2026-10-10T08:05:12Z", "expires_at": 1791900000}
```

Costs are computed on read (8 regions × 48 h is 384 footprints, a few
milliseconds), so changing a coefficient takes effect immediately with no
backfill. `ci_source` and `weather_source` travel with every row, so the
dashboard can say when a value is modelled or synthetic.

**Job** (`PK = JOB#<id>`, `SK = META`): the request, `status`
(`placed`, `infeasible`, then `running`, `done` or `failed` from Step 7), the
placement (chosen, baseline, alternatives, reason) and a preview receipt
from the modelled energy.

**Receipt** (`PK = RECEIPT#<job>`, `SK = META`): written by the executor after
the run, with measured kWh. Also archived to S3.
