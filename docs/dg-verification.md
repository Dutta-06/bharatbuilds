# DG-Shift implementation and verification record

## Reconnaissance and baseline

The checkout was main, with only an unrelated untracked .vscode directory.
No AGENTS.md or existing facility/DG implementation was found. Existing job
records, forecast/surface scheduler, DynamoDB PK/SK/GSI1 helpers, Lambda HTTP
handlers, Cognito platform-leads convention, run state machine and React hash
navigation were reusable. Missing pieces were facility configuration/state,
power telemetry/idempotency, a deadline/capacity gate, simulated lifecycle,
generator demand accounting and the operations UI.

The original executor was a CPU proxy, with no GPU checkpoint adapter. Split
plans were advisory. CloudFormation identities and table keys needed preservation.
The minimal integration added a facility gate around existing placement and
launch, with simulated facility jobs stored as normal JOB records. Expected file
areas were backend, scheduler, Lambda functions, SAM/ASL, dashboard, tests,
scripts and docs; no replacement application or database was introduced.

Initial python -m pytest -q failed collection (five errors, missing moto).
Data validation passed with zero errors and 42 existing coefficient/source
warnings. Initial npm ci was blocked by an uncached dependency; npm test hit
Windows spawn EPERM; build lacked vite after the incomplete install. GNU Make
and SAM were absent and Docker Desktop was stopped. Once dependencies were
installed, existing Windows worker tests failed on the Unix-only resource
module, split tests lacked OR-Tools, and notebook freshness depended on Git's
CRLF checkout. The worker CPU timer and text embedding were made portable.
Local HTTP integration exposed an existing unresolved RunStateMachine ARN;
env.local.json now explicitly disables local Step Functions startup unless a
valid local/deployed ARN is configured.

## Implemented phases

1. Facilities use the existing table and associated existing job identities.
2. The deterministic policy respects criticality, runtime/overhead, deadlines,
   dependencies, capacity and region/residency placement constraints.
3. Conditional transactions commit facility/jobs/events/decision history together.
   Event IDs and simulation generations make replay/reset safe.
4. IoT publish/rule/Lambda permissions, an S3 ingestion-error action and SNS async
   failure handling are configured in SAM; EventBridge reevaluates every minute.
5. Waiting cloud jobs use the same execution and a conditional launch guard.
   Running proxies are never paused. Simulated jobs checkpoint/resume only in
   their labeled domain adapter. Execution notification follows confirmed work.
6. Piecewise kW-seconds integration produces 42 kWh over 90 minutes; unsupported
   fuel/emission claims are omitted. INFEASIBLE work is not credited as a confirmed
   environmental deferral, and impossible critical demand is not counted protected.
7. Power & Operations uses real API calls, existing styles and hash navigation.
   Queue/Job safely render the same simulated records; public controls require
   platform-leads or an explicitly local SAM configuration.
8. Offline replay, persistent LocalStack, SAM HTTP checks and a real Edge browser
   demo are reproducible with committed scripts. All original resource definitions
   in template.yaml compare equal to HEAD; only five new resource definitions were added.

## Final quality review

Cloud architecture: SAM lint/build passed; IoT invocation is scoped to source
rule/account, publishing is topic scoped, and DynamoDB accesses use existing
keys and scoped permissions. No AWS deployment or resource recreation occurred.

Distributed systems: duplicate events, competing versions, failed commits,
failed recovery, reset generations, completion races and launch claims were tested.
DG never cancels/restarts an execution; the existing reschedule endpoint rejects
facility jobs. Uncertain worker transport/service failures never trigger a second
fallback launch. Worker results are reused, and same-status updates invalidate
stale facility snapshots. A failed uncertain launch requires reconciliation.

Optimization: deterministic ordering preserves critical services and evaluates
runtime plus overhead before deferral. Latest safe resume boundaries are revisited
without assuming restoration. Dependency/residency/max-delay violations and
insufficient capacity produce explicit INFEASIBLE explanations. Recovery applies
hysteresis and capacity ordering, with Tidewise forecasts for cloud placements.

Environmental accounting: 55 -> 27 kW and 28 kW deferral are verified, as is
28 * 5400 / 3600 = 42 kWh. ETL completion changes the later current baseline to
47 kW, so the later demand is 47 -> 19 kW. IT demand is MODELED and facility
execution SIMULATED. No meter readings, diesel reduction percentage or pollutant
quantities are asserted. Optional sourced fuel curves interpolate only within
supported loading points; no double counting enters Tidewise receipts/Savings.

## Checks and live verification boundary

Recorded results:

| Command/check | Outcome |
|---|---|
| python -m pytest -q -rs | 212 passed, 1 optional Strands SDK test skipped; followed by targeted tests for the final identity/deadline fixes |
| python -m pytest tests/api -q | 87 passed after identity and notification-flow fixes |
| python -m pytest tests/api/test_facilities.py -q | 30 passed after the final late-completion/deadline fix |
| python scripts/validate_data.py --quiet | 0 errors, 42 existing warnings |
| python -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --temp 33 --rh 65 --ci 680 | Passed with PYTHONUTF8=1 on Windows |
| npm ci --offline=false --cache .npm-cache | Passed (locked dependencies) |
| npm test | 9 passed, 0 failed |
| npm run build | Passed |
| python -m samcli validate --template template.yaml --lint | Passed |
| python scripts/build_backend.py, subsequent python -m samcli build | Passed, including Linux Python 3.12 assistant/core layers |
| python scripts/facility_demo.py offline-replay | Passed full state/action/energy and duplicate assertions |
| LocalStack setup/offline seed/persistent event replay | Passed |
| python scripts/verify_facility_api.py | Passed actual SAM HTTP facility lifecycle and existing Surface/job endpoints |
| node dashboard/scripts/verify_operations.mjs (from dashboard: node scripts/verify_operations.mjs) | Passed actual Edge controls, numerical results, recovery, mobile Queue/Job navigation and API error feedback |
| git diff --check | Passed |
| Existing CloudFormation resource comparison against HEAD | All existing resource definitions identical; five additions |

Host checks used workspace-local dependencies via PYTHONPATH=.test-deps. SAM's
Windows Docker SDK additionally needs its win32, win32/lib and pywin32_system32
paths when installed with pip --target. The dashboard runs at
http://127.0.0.1:5173/#/operations and SAM at http://127.0.0.1:3000. LocalStack is
healthy on port 4566. The demonstration was reset to GRID after verification.
AWS deployment, live IoT ingestion, production Cognito and live Step Functions
power recovery were NOT RUN: the task does not authorize deployment. The smallest
remaining action is an approved account/region/stack change-set review, deployment,
then an actual --iot event and authenticated dashboard/worker verification.

GNU Make is unavailable on this Windows host, so literal make ci and make build
were not run. Their component checks and the portable build_backend.py/SAM build
were run instead. One existing optional Strands SDK import test is skipped in the
host test environment. Its package is included in the built assistant Lambda layer;
this does not count as a host test pass or a live assistant-model verification.

The private facility administrative UI is outside the MVP: public GETs expose
only the seeded public demo. IAM CLI/backend provisioning and sensor processing
support nonpublic sites. Physical generator telemetry and GPU checkpoint control
remain outside scope by design. The bounded facility registry supports at most
20 associated jobs per facility. Live infrastructure throughput needs verification
before broadening this hackathon deployment.
