# Architecture

```mermaid
flowchart LR
  subgraph Sources
    OM[Open-Meteo<br/>temperature, RH, pressure]
    EM[Electricity Maps<br/>carbon intensity, mix]
  end

  subgraph Hourly["pravaah-forecast (Step Functions, hourly via EventBridge)"]
    F[fetch_forecast] --> P[predict<br/>Step 4 models] --> S[store_forecast]
  end
  OM --> F
  EM --> F
  F -- raw JSON --> S3[(S3<br/>raw forecasts, receipts)]
  S --> DDB[(DynamoDB<br/>pravaah-main)]

  subgraph API["HTTP API (API Gateway + Lambda) behind CloudFront"]
    GS[GET /surface]
    SJ[POST /jobs]
    GJ[GET /jobs, /jobs/:id]
    GR[GET /jobs/:id/receipt]
  end
  DDB --> GS
  DDB --> GJ
  DDB --> GR
  SJ -- score + schedule --> DDB

  subgraph Run["pravaah-run (Step Functions, one per job)"]
    L[load] --> W[Wait until<br/>chosen hour] --> X[launch] --> R[finish:<br/>receipt]
  end
  SJ -- start --> L
  X -- cross-region invoke --> WK[pravaah-worker<br/>in the chosen region]
  R --> DDB
  R --> S3
  Run -- placed / started / finished --> SNS[SNS<br/>email]

  UI[Dashboard<br/>React on Amplify] --> API
  CW[CloudWatch<br/>dashboard + alarms] -.-> Hourly
  CW -.-> Run
```

**The cost model** (`model/`) and **the scheduler** (`scheduler/`) are plain Python
libraries. The same code runs in the CLI, the tests, the trace replay and the Lambdas
(packaged in one layer).

**Every number has a source** (`model/coefficients.yaml`). **Every forecast row carries
where it came from** (`weather_source`, `ci_source`, `t_wb_source`). The dashboard shows
when anything is synthetic or modelled.

## Facility power integration

The simulator publishes to AWS IoT Core; its rule invokes the power-event Lambda.
A shared deterministic gate commits facility state, existing JOB records, event IDs
and decisions atomically to the existing table. EventBridge reevaluates deadline
boundaries every minute. Waiting cloud jobs remain in the same run state machine
and use its conditional launch guard; running proxies are never paused.
React Power & Operations reads persisted state and authenticated controls publish
through IoT. Facilities are physical sites, never whole AWS regions.
See [DG-Shift operation and limitations](dg-shift.md).
