# Tidewise: scheduling AI jobs for the least water and carbon

## The problem

Data centres cool servers by evaporating water, and the hotter and more humid the air, the more they use. The grid
adds its own water (thermal power plants) and carbon. Both vary a lot by place and hour. At the time of writing, one kWh
of AI compute in Mumbai takes about **4.7 litres of water and 0.8 kg of CO₂**; in Stockholm, about **1.0 litre and
0.03 kg**, roughly 5× the water and 30× the carbon.

Most AI work (training, fine-tuning, batch inference, evaluation sweeps) has a deadline of hours or days, not seconds.
That slack is a free lever, and carbon-aware schedulers already use it. Almost none consider water, and water and
carbon do not always agree: a nuclear-heavy grid is clean but thirsty.

## What we built

**Tidewise** decides where and when to run a job, then proves what that saved.

- **Forecast.** Every hour it forecasts wet-bulb temperature and grid carbon for eight AWS regions, 48 hours ahead, and
  prices every region-hour in litres of water and kilograms of CO₂, with uncertainty ranges. A learned forecast is used
  only where it beats a simple baseline.
- **Schedule.** Given GPU-hours, a deadline and optional limits (allowed regions, data residency, maximum delay,
  water-versus-carbon weights), it searches every region and start hour that still meets the deadline and picks the
  cheapest. It explains the choice in plain language and lists the alternatives it considered.
- **Run and receipt.** The job waits for its hour, runs in the chosen region, and gets a shareable receipt: modelled
  litres and kilograms saved against running immediately in the submit region. Waiting jobs are re-checked as forecasts
  change, and a better window triggers an email nudge or a one-click reschedule.
- **Around it.** Team policies, cumulative savings, a plain-language assistant, in-app documentation and an API.
- **DG-Shift.** A facility power module for generator backup: it protects critical services, defers flexible work and
  recovers within deadlines. This part is a simulation, and is labelled as one.

**Example from the live system:** a 4 GPU-hour job submitted from Mumbai was placed in Stockholm, with 79% less water
and 97% less CO₂ than running immediately. A job placed through the assistant ran in Ireland, with 95% less water and
73% less CO₂.

## Where AWS fits

| Need | AWS service |
|---|---|
| Hourly forecast pipeline | EventBridge schedule → Step Functions → Lambda |
| One workflow per job: wait for the chosen hour, launch, receipt, notify | Step Functions (Wait state) + Lambda |
| Running the workload in the chosen region | Lambda worker deployed in every region jobs can run in |
| API | API Gateway (HTTP API) + Lambda, throttled |
| Jobs, forecasts, receipts, facility state | DynamoDB single table; S3 for stored copies and public surface data |
| Email alerts and nudges | SNS |
| Sign-in and team-policy permissions | Cognito (`platform-leads` group) |
| Facility power telemetry | IoT Core → Lambda → DynamoDB |
| Dashboards and alarms | CloudWatch |
| Front end | Amplify |

Everything is defined in one AWS SAM template and deployed to ap-south-1. The AWS regions themselves are the thing being
scheduled across, so AWS is both the platform and the subject.

## What we are careful about

- Water and carbon are **modelled** from published cooling curves, weather and grid forecasts. Absolute litres are
  uncertain; the ranking of slots is more robust. Receipts show ranges.
- Lambda has no GPUs, so the workload that actually runs is a CPU stand-in whose energy is measured; the declared GPU
  job's energy is estimated. Receipts say which is which.
- We do not control any data centre. Tidewise chooses placements; it does not claim measured savings.
