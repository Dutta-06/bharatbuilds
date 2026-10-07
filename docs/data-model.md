# DynamoDB data model

One table, `chhaanv-main`, with a generic primary key (`PK`, `SK`), one global
secondary index (`GSI1PK`, `GSI1SK`), and TTL on `expires_at`.

## Access patterns

These were written before the code. Every query the system makes is listed here.

| # | Who | Pattern | Key condition |
|---|---|---|---|
| 1 | `compute_risk` | Write 48 hourly risk rows for a cell | `PK = CELL#<city>#<cell>`, `SK = HOUR#<local iso>` (batch put) |
| 2 | `get_risk` | Read the next 48 h for a cell | `PK = CELL#<city>#<cell>` and `SK BETWEEN HOUR#<now> AND HOUR#<now+47h>` |
| 3 | `compute_risk` / `detect_transitions` (Step 4) | Latest run for a cell | `PK = CELL#<city>#<cell>`, `SK = META#latest` |
| 4 | `subscribe` | Save a subscription | `PK = USER#<device id>`, `SK = SUB#<city>#<cell>` |
| 5 | Frontend | List a device's subscriptions | `PK = USER#<device id>`, `SK begins_with SUB#` |
| 6 | `send_alerts` (Step 7) | Who is subscribed to a cell? | GSI1: `GSI1PK = SUBS#<city>#<cell>` |
| 7 | Step 8 | Reports and relief points in a cell | `PK = REPORT#<city>#<cell>` (reserved, not built yet) |

## Items

**Risk hour**, one per cell per hour, holding both hazards:

```json
{
  "PK": "CELL#delhi#rohini", "SK": "HOUR#2026-05-26T14:00",
  "city": "delhi", "cell_id": "rohini", "time": "2026-05-26T14:00",
  "heat": {"metric": "wbgt", "value": 31.4, "light": "red", "moderate": "red", "heavy": "red"},
  "waterlogging": {"rain_mm": 0.0, "level": "green"},
  "run_id": "2026-05-26T14:00Z", "computed_at": "2026-05-26T08:31:02Z",
  "expires_at": 1780000000
}
```

Heat is stored for all three work intensities. The WBGT is computed once and
banded three ways, so a read never needs to recompute. Times are local to the
city (`Asia/Kolkata` for Delhi), stored as naive ISO strings so they sort
correctly as `SK`. Rows expire two days after their hour.

**Run marker** (`SK = META#latest`): `run_id`, `computed_at`, `first_hour`, `last_hour`.

**Subscription**:

```json
{
  "PK": "USER#3f2c...", "SK": "SUB#delhi#rohini",
  "GSI1PK": "SUBS#delhi#rohini", "GSI1SK": "USER#3f2c...",
  "work": "heavy", "lang": "hi", "hazards": ["heat", "waterlogging"],
  "channel": "email", "contact": "someone@example.com",
  "status": "pending_confirmation", "created_at": "..."
}
```

## Why one row per cell-hour (not one per cell-hour-hazard)

Writes are the main cost. 61 cells × 48 hours is 2,928 writes per hourly run,
which fits inside DynamoDB's burst capacity on the always-free 25 WCU
provisioned tier. Splitting by hazard would double that to 5,856 writes per run
and start to throttle. The Step 4 hazard branches compute in parallel and hand
their results to a single write.
