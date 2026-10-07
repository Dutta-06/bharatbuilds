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
