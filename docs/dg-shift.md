# Tidewise Power & Operations

Tidewise schedules flexible AI workloads across time and location to reduce water
and carbon impact. During diesel-generator backup, its DG-Shift capability
protects critical workloads, defers eligible nonurgent computation, and
reschedules work after stable grid recovery.

## Scope and execution

A facility is a physical monitored site, **not an AWS region**. Only job records
explicitly linked by `facility_id` enter its policy. Existing jobs have no default
facility and keep normal scheduling. There is no second job database.

The demo uses `SIMULATED_FACILITY` jobs in the existing queue. Their running,
deferred, resumed and completed states persist in DynamoDB. No GPU or AWS process
is checkpointed. `CLOUD_PROXY` uses the existing actual CPU worker and receipts.
Running proxies cannot be paused. Waiting proxies use a transactional launch
guard in the existing Step Functions execution: wait 60 seconds, reread the gate,
and launch once. DG operations never cancel an execution. Manual forecast
rescheduling is disabled for associated jobs, avoiding competing controllers.

The cloud launch claim is conditional on waiting/placed job state and the facility
version. A saved worker result is reused on retry. An uncertain worker failure
after a successful claim is not relaunched automatically; operator reconciliation
is required. This prioritizes no duplicate execution over speculative retries.

## Event pipeline and correctness

Authenticated simulator → Boto3 IoT Data publish (QoS 1) →
`tidewise/facilities/<facility_id>/power` → IoT rule → power Lambda → shared
domain handler → single-table transaction → workload/decision state → dashboard.
The rule verifies topic/payload association; invocation permission is restricted
to the rule ARN and account. CloudWatch logs record accepted/rejected events.
Lambda async failures use the existing SNS topic as a dead-letter destination.
EventBridge reevaluates facilities every minute for deadlines and recovery.

```json
{
  "event_id": "unique-event-id",
  "facility_id": "demo-delhi-01",
  "power_state": "GENERATOR",
  "observed_at": "2026-10-10T09:30:00Z",
  "source": "simulator",
  "generation": "read-this-from-the-current-demo-facility"
}
```

All times require a timezone and are normalized to UTC. Timestamp examples are
examples only. Real telemetry must be within the configured maximum age (default
300 seconds), strictly later than the last accepted observation, and not earlier
than accounted state. Simulator time is explicit and reproducible, not wall time.
A reset rotates its generation; old messages cannot change the new demonstration.
Devices need independent, least-privilege IoT publishing credentials; frontend
code holds no AWS keys. Real facilities reject `source: simulator`.

Transitions: GRID → BATTERY_TRANSITION or GENERATOR; BATTERY_TRANSITION → GENERATOR
or GRID_RECOVERY; GENERATOR → GRID_RECOVERY; GRID_RECOVERY → GRID after hysteresis
or GENERATOR on flicker. Same-state observations reevaluate without resetting
hysteresis. Returning directly from GENERATOR to GRID is rejected.

Facility version, each job's status/power version, the durable event marker and
the entire decision batch commit atomically. A repeated identical event returns
its original version without actions; reused IDs with changed payloads conflict.
Concurrent writes retry with fresh reads up to four times, then return conflict.
AWS failures propagate; no successful action is reported before commit. Event
IDs remain durable without TTL. Registry/job lists are bounded to 20 jobs per
facility for this MVP. DynamoDB limits and table capacity need review before
larger deployments. Public views expose only the explicit public demo.

## Scheduling and recovery

Deterministic priority: critical service protection, hard deadline/dependencies,
capacity, power policy, then Tidewise environmental placement for cloud recovery.
No residency or allowed-region constraints are relaxed and facility jobs are not
implicitly relocated. A dependency must reference a completed associated job.
Missing dependencies block execution. Critical blocked dependencies and mandatory
demand exceeding capacity produce explicit INFEASIBLE decisions.

CRITICAL means mandatory continuous service. DEADLINE means a finite job whose
slack must permit the decision horizon before it can wait. CHECKPOINTABLE allows
pause only when the adapter supports it (the simulated adapter in this MVP).
INTERRUPTIBLE permits modeled pause/restart; real running proxies remain
non-preemptible. Optional cloud metadata defaults to DEADLINE, CLOUD_PROXY,
checkpoint unsupported, zero overhead and no dependencies. Power must be supplied
explicitly in kW. Remaining runtime uses the existing job duration; deadline stays
in the existing request. Checkpoint and resume overheads use seconds and are
charged once when a simulated checkpoint occurs.

Generator deferral requires slack greater than one configurable decision horizon
(default 30 minutes), including overhead. No grid restoration time is assumed.
The simulator advances through decision horizons, completion times, latest safe
resume boundaries and recovery boundaries. Long outages resume eligible work
before deadlines; insufficient capacity or an impossible runtime is reported,
not hidden. Periodic real reevaluation has up to one minute of EventBridge latency;
the launch gate always reevaluates again before execution.

Recovery waits for stable-grid hysteresis, 30 seconds **only for the explicit
demo**, at least 300 seconds for real provisioning. Deadline urgency overrides
optional recovery delay. Work is ordered by criticality, deadline and job ID;
capacity queues stagger modeled restarts until capacity becomes available.
Waiting cloud jobs are replanned with the existing Tidewise forecast scheduler,
preview receipts are recalculated, and their original execution waits for the
new placement. Simulated local facility work has no regional water/carbon forecast
and is not assigned an invented AWS footprint. INFEASIBLE remains a decision,
not confirmation that a physical workload stopped.

## Environmental accounting

The demo starts at 55 kW IT demand. API 7, database 8 and authentication 4 kW
continue; ETL 8 kW continues because its 45-minute runtime and one-hour deadline
leave only 15 minutes of slack. Training 18 kW is checkpointed **SIMULATED** and
backup 10 kW deferred. Demand becomes 27 kW, a 28 kW (50.9%) modeled IT reduction.

Deferred IT electricity demand = deferred kW × elapsed seconds / 3600.
28 kW for 5400 seconds = **42 kWh**. Integration is piecewise at lifecycle
boundaries. ETL finishes during the 90-minute example, so current demand afterward
is 47 → 19 kW; the generator activation snapshot remains 55 → 27 kW.
The 5 kW base-load assumption is excluded from IT demand but included in any
conditional generator-loading estimate. This is shifted computation, not
permanent avoided energy, generator output, diesel fuel or pollutant reductions.
Generator accounting never enters Tidewise's water/carbon receipts or Savings.

Fuel estimates are UNAVAILABLE by default. Optional `fuel_curve` contains a
manufacturer `source` and ordered `points` of `load_fraction` and
`litres_per_hour`. Only interpolation within documented points is supported;
out-of-range demand is rejected, never extrapolated. A valid curve yields a
conditional MODELED rate, not measured fuel savings. No diesel CO2, PM2.5, NOx
or black-carbon numbers are asserted. The demo telemetry/lifecycle is SIMULATED,
IT power/energy is MODELED, no generator MEASURED or PROVIDER-DERIVED quantities
are available. Existing Tidewise forecasts retain their own source labels.

## APIs and authorization

GET /facilities lists public demo facilities. GET /facilities/{id} returns
`facility` and `workloads`. GET /facilities/{id}/decisions returns the latest 30
immutable decision batches. Public responses omit DynamoDB keys for the facility
and job records. Private facilities return 404 on public views.

POST /facilities/{id}/simulate-power requires Cognito JWT plus `platform-leads`:

```json
{"power_state": "GENERATOR", "advance_s": 1, "event_id": "optional-unique-id"}
```

Omit power_state to advance the existing state. `advance_s` is 1–86400 seconds.
`{"operation":"reset"}` resets only demo-delhi-01. Reset commits directly;
deployed power mutations publish through actual IoT Core and return 202 PENDING,
not confirmation of execution. Poll facility state/last_event_id. A topic rule
or policy rejection appears in Lambda logs, not as a synchronous publish failure.
The CLI prints the exact event for inspection/replay. For transport retries that
need identical payloads, republish that exact JSON with the same event ID and
generation; generating a new timestamp with a reused ID correctly conflicts.

Outcomes: 200 reads/reset/local accepted event; 202 published event; 400 invalid
inputs; 401 missing auth; 403 wrong group/non-simulated mutation; 404 unknown or
private site; 409 invalid transition, stale/out-of-order/conflicting event or
concurrent writes. Identical duplicate domain events return 200 with duplicate
true. Infrastructure failures raise for retry and appear as API 5xx, never success.
Public POST /jobs rejects facility association: trusted IAM backend/CLI provisioning
is required because that existing route has no JWT authorizer. Unassociated job
submission and existing response fields remain unchanged.

## Reproducible offline demonstration

```bash
pip install -r requirements-dev.txt
python scripts/facility_demo.py offline-replay
```

This requires no generator, Docker, AWS account or network after installing
dependencies. It runs the same domain handlers and transaction logic against
Moto DynamoDB, checks duplicate delivery, 27 kW, 42 kWh and recovery. Moto is
an emulator, not live AWS verification. The script exits when the replay ends.

## Interactive local dashboard

Requires Docker running, SAM CLI, GNU Make and Python 3.12.

```bash
make local-up
make local-setup
make seed SEED_ARGS=--offline
make api
```

In another terminal:

```bash
cd dashboard
# PowerShell: $env:VITE_DG_LOCAL_SIMULATION='true'
VITE_DG_LOCAL_SIMULATION=true npm run dev
```

Open http://localhost:5173/#/operations. `env.local.json` enables the backend
local mode only when AWS_SAM_LOCAL=true. The frontend local override is restricted
to localhost and a localhost API. It cannot authorize deployed mutation routes.
Reset → Grid failure → Activate generator → Advance 90 minutes → Restore grid →
Confirm stable grid. All state and controls use the real Lambda HTTP API, no
frontend mock state. Local SAM JWT authorizer emulation may vary by SAM version;
trusted CLI reset/event commands below also work against LocalStack.

```bash
export AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=ap-south-1 TABLE_NAME=pravaah-main
python scripts/facility_demo.py reset
python scripts/facility_demo.py event --state GENERATOR
python scripts/facility_demo.py event --advance-s 5400
python scripts/facility_demo.py event --state GRID_RECOVERY
python scripts/facility_demo.py event --advance-s 30
python scripts/facility_demo.py show
```

## AWS prerequisites and three-minute presentation

No deployment is automatic. Review SAM/CloudFormation change sets against the
approved account, region and existing stack. All existing logical identities,
table keys, indexes and pravaah-prefixed resource names are retained. New IoT
resources require supported AWS IoT Core region, IAM deployment permissions,
IoT endpoint discovery/publish rights, and device authentication for real telemetry.
The simulator uses IAM-authenticated HTTPS publish to the IoT MQTT topic.

After an approved deployment, configure the existing VITE_API_URL,
VITE_COGNITO_REGION and VITE_COGNITO_CLIENT_ID. Sign in as platform-leads.
For an IAM-authenticated terminal with TABLE_NAME and AWS_DEFAULT_REGION set:

```bash
python scripts/facility_demo.py reset
python scripts/facility_demo.py event --state GENERATOR --iot
```

CLI trusted provisioning: `python scripts/facility_demo.py provision --file facility.json`;
cloud submission: `python scripts/facility_demo.py submit-cloud --file job.json`.
Set RUN_STATE_MACHINE_ARN for actual Step Functions startup. Without it, submission
persists a placement but does not execute. No credentials are printed or stored
in the frontend. Provision never overwrites existing facilities.

0:00–0:30 show existing Submit/Surface water/carbon placement. 0:30–0:50 open
Power & Operations and Reset. 0:50–1:10 Grid failure then Activate generator.
1:10–1:50 show 55 → 27 kW, 28 kW deferral and explanations. 1:50–2:15 explain
training's simulated checkpoint, ETL's deadline and protected services; advance
90 minutes to show 42 kWh. 2:15–2:40 Restore grid then Confirm stable grid.
2:40–3:00 show resumed work, unchanged cumulative deferred energy, and explain
which AWS components actually ran. On an offline/local presentation explicitly
say IoT Core and deployed AWS verification were NOT RUN.

## Windows verification and local configuration

On Windows without GNU Make, `python scripts/build_backend.py` packages the
existing layers and runs SAM build. Docker and the Python 3.12 launcher are
required. The assistant dependencies are resolved on Linux and transferred as
one archive to avoid slow Windows bind-mount copies. This does not deploy.

Local `env.local.json` explicitly leaves RUN_STATE_MACHINE_ARN empty, so normal
HTTP submissions place/persist jobs but do not start an unresolved state machine.
Provide a valid ARN in an approved environment for actual cloud execution.
Use warm containers for responsive presentations:

```bash
sam local start-api --template template.yaml --env-vars env.local.json --docker-network pravaah --warm-containers LAZY
python scripts/verify_facility_api.py
cd dashboard
npm install --no-save --package-lock=false playwright
node scripts/verify_operations.mjs
```

The optional browser check uses Edge on Windows (Chromium elsewhere), drives
actual backend controls, checks mobile navigation, and injects one network failure
to verify error feedback. Stop the browser check before presenting; it resets
the demonstration. For a fresh normal state press Reset again.

Real sensor observations are ordered by observed_at, while workload decisions
apply at receipt time. Delayed but fresh observations remain acceptable after a
periodic accounting tick. Already-accounted intervals are not rewritten; this
conservative modeled accounting is not measured facility electricity. Generator
accounting includes simulated deferred jobs and cloud jobs held by the launch
guard, never unsupported physical pauses or INFEASIBLE jobs as environmental gains.
The generator baseline represents eligible modeled demand, not meter readings.

The IoT rule stores ingestion-action errors under power-events/errors/ in the
existing S3 bucket. Async Lambda failures use SNS; inspect these destinations and
CloudWatch before replaying an unconfirmed event. Simulator requests with the
same event_id and identical parameters reuse the original accepted telemetry;
changed parameters conflict. Direct device publishing must reuse exact JSON for
transport retries. Reset is refused if additional cloud workloads were associated
with the demo, preventing orphaned jobs. Use a separate provisioned site for cloud
integration experiments.

Submissions now return 409 when a job ID already exists, preventing public callers
from overwriting demo or other workload records. Execution confirmation is sent
only after the launch guard permits work; notification failure does not prevent
receipt finalization.

Facility association is explicit policy metadata, not proof that an AWS Lambda
worker occupies the monitored physical building. The proxy demonstrates cloud
launch coordination; generator-period IT demand uses declared facility workload
power, never inferred Lambda CPU measurements. No AWS-region diesel state is inferred.
