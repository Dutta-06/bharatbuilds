# Chhaanv — Build Plan

Heat and Water risk layer for Indian cities. Environmental Hacks (Bharat Builds Tour, event 02), Heat and Water track.

Steps are ordered by dependency, not by day. Each step has a goal, tasks, the AWS pieces it introduces, and a "done when" check. Do not start a step until the one it depends on is done. Steps marked **Core** must ship. Steps marked **Expand** ship if Core is stable. Steps marked **Design only** get a slide in the video if not built.

---

## Step 0 — Setup and eligibility (Core)

**Goal:** Everyone can build and nothing blocks the submission later.

- [ ] Every team member verifies student status on AWS Builder Center (required to compete).
- [ ] Team leader checks in on the WeMakeDevs hackathon page; apply on Luma separately if attending DTU.
- [ ] Create one AWS account for the team (free tier, debit/RuPay card, ~₹2 verification). Enable MFA. Set a billing alarm at $5 and $20.
- [ ] Create an IAM user or role for each member; nobody uses root.
- [ ] Create the GitHub repo: `chhaanv/`. Branch protection on `main`, PRs for everything.
- [ ] Install locally: Python 3.12, Node 20, AWS CLI, SAM CLI, Docker (for LocalStack), Finch is optional.
- [ ] Agree on the stack: Python for all Lambdas, React + Vite for the frontend, Leaflet for maps.
- [ ] Create a shared doc for the demo script and the Builder Center blog outline; add to it as you go.

**Done when:** every member can `sam build` the empty template and `aws sts get-caller-identity` returns the team account.

---

## Step 1 — Risk engine (Core)

**Goal:** A pure-Python library that converts a weather forecast into a risk level. No AWS yet. This is the thing the judges are actually scoring.

- [ ] `engine/wbgt.py`: estimate WBGT from temperature, relative humidity, solar radiation, wind speed (Australian BoM approximation; document the formula and its limits in a docstring).
- [ ] `engine/heat_index.py`: NOAA heat index as a fallback when solar data is missing.
- [ ] `engine/thresholds.py`: risk bands per work intensity (light / moderate / heavy), based on ISO 7243. Output: `green | amber | red`.
- [ ] `engine/windows.py`: given 48 hourly risk levels, produce plain-language safe windows in English and Hindi. Keep the strings in a JSON file, not in code.
- [ ] `engine/waterlogging.py`: rainfall intensity thresholds (mm per 3 h) crossed with hotspot membership and elevation. Output the same `green | amber | red` shape.
- [ ] Unit tests for every function with known inputs (a 44°C/60% RH afternoon must be red for heavy work; a 28°C morning must be green).
- [ ] A CLI: `python -m engine --lat 28.7 --lon 77.1 --work heavy` that prints the strip from a live Open-Meteo call.

**Done when:** tests pass, the CLI prints a believable 48-hour strip for Delhi, and one person who did not write it can explain the thresholds.

---

## Step 2 — City grid and static data (Core)

**Goal:** The fixed set of cells the whole system keys on, plus the open data each hazard needs.

- [ ] Define the Delhi NCR grid: roughly 50 cells, each with an id, centroid lat/lon, and a human name (the locality people actually say: Rohini, Dwarka, Okhla).
- [ ] `data/cities/delhi.json`: the grid plus city bounds. Adding a city must be adding a file.
- [ ] Collect the Delhi waterlogging hotspot list (PWD/MCD/Traffic Police publish these) and map each hotspot to a cell. Store as `data/hotspots/delhi.json` with source links.
- [ ] Pull elevation per cell centroid from Open-Meteo's elevation API once; store it in the grid file.
- [ ] Seed relief points: a handful of real piyaos, parks, and shelters so the map is not empty in the demo.
- [ ] A script that validates all data files against a JSON schema.

**Done when:** `python scripts/validate_data.py` passes and a map of the grid rendered in a notebook looks like Delhi.

---

## Step 3 — Local infrastructure with SAM and LocalStack (Core)

**Goal:** The full serverless backend running on a laptop before any cloud spend.

- [ ] SAM template skeleton: one DynamoDB table (`chhaanv-main`, single-table design), one S3 bucket, the Lambda functions below, an HTTP API.
- [ ] DynamoDB keys: `PK = CELL#<id>`, `SK = HOUR#<iso>` for risk; `PK = USER#<id>` for subscriptions; `PK = REPORT#<cell>` for reports and relief points. Write the access patterns down before writing code.
- [ ] Lambda `fetch_forecast`: calls Open-Meteo for one cell, returns raw hourly data.
- [ ] Lambda `compute_risk`: runs the engine for one cell, writes 48 rows to DynamoDB.
- [ ] Lambda `get_risk`: `GET /risk?lat&lon&work` — finds the nearest cell, returns the strip and windows.
- [ ] Lambda `subscribe`: `POST /subscribe` — stores cell, work intensity, channel, contact.
- [ ] LocalStack config so DynamoDB and S3 run locally; `sam local start-api` serves the HTTP API.
- [ ] A `make seed` target that runs the pipeline for all cells locally.

**Done when:** `curl localhost:3000/risk?lat=28.7&lon=77.1&work=heavy` returns a correct strip from locally seeded data.

---

## Step 4 — Hourly pipeline with Step Functions (Core)

**Goal:** The thing that keeps the data fresh without anyone touching it.

- [ ] State machine `chhaanv-hourly`:
  1. Load grid from S3.
  2. Map state over cells (concurrency 10): `fetch_forecast` → `compute_risk` (parallel branches per hazard: heat, waterlogging).
  3. `detect_transitions`: compare the next hour to the previous run; emit a list of (cell, hazard, level) changes.
  4. Push each change to an SQS queue.
- [ ] EventBridge rule: run the state machine every hour on the hour.
- [ ] Retries and a catch-all failure state that writes to CloudWatch Logs.
- [ ] A manual "run now" trigger for demos.

**Done when:** the state machine runs end to end on LocalStack or in AWS, the DynamoDB table has 48 rows per cell per hazard, and a forced change lands in SQS.

---

## Step 5 — Deploy to AWS (Core)

**Goal:** A public URL, early, so everything after this is iterated live.

- [ ] `sam deploy --guided` to the team account, `ap-south-1` (Mumbai).
- [ ] Run the hourly pipeline once; confirm data in DynamoDB.
- [ ] HTTP API behind CloudFront with a cache of 5 minutes on `GET /risk`.
- [ ] CloudWatch dashboard: state machine success/fail count, Lambda errors, API latency, rows written per run.
- [ ] Billing check: everything should sit inside free tier; confirm the cost explorer shows ~$0.

**Done when:** `curl https://<api>/risk?...` works from a phone on mobile data.

---

## Step 6 — Worker frontend (Core)

**Goal:** The screen a worker sees. Mobile-first, Hindi default, usable on a ₹6,000 phone.

- [ ] React + Vite, deployed on Amplify Hosting with the API URL as an env var.
- [ ] Onboarding: pick a locality (searchable list from the grid), pick work intensity, pick language. Three taps, no account.
- [ ] Home: a 48-hour colour strip (big blocks, hour labels), the safe-window sentence in large text, the current risk level as a single word.
- [ ] Hazard tabs: Heat, Waterlogging (same strip, different data).
- [ ] Relief map: Leaflet + OpenStreetMap tiles, markers for water points and shade, "add a spot" button.
- [ ] Subscribe: email now, web push if time allows. Store a device id in localStorage.
- [ ] All strings in `i18n/en.json` and `i18n/hi.json`; nothing hardcoded.
- [ ] Lighthouse mobile score above 80; test on an actual low-end Android.

**Done when:** a stranger with the URL can pick Rohini, see today's red hours for heavy work, and subscribe, with no help.

---

## Step 7 — Alerts (Core)

**Goal:** The alert arrives before the danger, not after.

- [ ] Lambda `send_alerts`: consumes the SQS queue, looks up subscriptions for the (cell, hazard), composes a message in the user's language with one action line.
- [ ] SNS topic per channel; email subscriptions confirmed by the user.
- [ ] Web push via a VAPID key pair stored in Secrets Manager (or SSM parameter) if implemented.
- [ ] Lead time: alert at the transition one hour ahead, so it lands ~30–60 min before red.
- [ ] Dedupe: do not send the same (user, cell, hazard, level) twice within 6 hours.
- [ ] Shareable card: Lambda renders a PNG summary for a cell (Pillow), stored in S3, served via CloudFront, for forwarding into colony groups.

**Done when:** forcing a cell to red triggers one email to a subscribed address within a minute, and running it again sends nothing.

---

## Step 8 — Community reports (Expand)

**Goal:** Live ground truth on top of the forecast.

- [ ] `POST /report`: type (heat illness, flooding, dry tap, tanker arrived, relief point), cell, optional photo, optional note.
- [ ] Photos: presigned S3 upload from the browser; Lambda thumbnails them.
- [ ] `POST /report/{id}/confirm`: neighbours confirm; trust score = confirmations decayed by age.
- [ ] Reports feed back: `compute_risk` bumps a cell one level if 3+ confirmed reports of the matching hazard exist in the last 3 hours.
- [ ] Moderation: a simple deny list and a rate limit per device id.
- [ ] Reports visible on the relief map as a separate layer.

**Done when:** three confirmed flooding reports in a cell turn an amber cell red on the next pipeline run.

---

## Step 9 — Water scarcity layer (Expand)

**Goal:** The "too little water" half of the track.

- [ ] Supply board per locality: today's reported status (tap ran / tanker came / nothing) from Step 8 reports.
- [ ] Tanker tracker: a colony logs a tanker request; others see it exists and can add "still waiting" or "arrived."
- [ ] Heat + no-water flag: a cell that is red for heat with a majority "nothing" supply status gets a distinct warning and a higher civic priority.

**Done when:** the Rohini page shows a believable supply board from seeded reports.

---

## Step 10 — Roles, auth and policy (Expand)

**Goal:** Supervisors and schools without breaking the no-account worker flow.

- [ ] Cognito user pool for supervisors, school admins, and civic viewers only. Workers stay anonymous.
- [ ] Cedar policies: worker reads own data; supervisor reads crew cells; school reads own cells and can publish an advisory; civic reads everything, writes nothing. Keep them in `policies/*.cedar`, evaluated in a Lambda authorizer.
- [ ] Supervisor view: register a crew (cells + intensity), see today's red hours, one-tap "schedule a break" that creates a reminder alert for the crew.
- [ ] School view: timetable slots against the heat strip, "move indoors" advisory generator.

**Done when:** a supervisor can log in, see their crew's red hours, and a worker URL cannot reach the supervisor endpoints.

---

## Step 11 — Conversational assistant with Strands Agents (Expand)

**Goal:** Access for people who will not navigate a map.

- [ ] Strands agent with two tools: `get_risk(area, work, time)` and `find_relief(area)`, both calling the deployed API.
- [ ] System prompt that answers in the language of the question, keeps replies to two sentences, always includes an action.
- [ ] Run it in a Lambda behind `POST /chat`; add a chat box to the frontend.
- [ ] Test set of 20 Hindi and English questions with expected answers; the agent must pass 16.

**Done when:** "kya main 2 baje Rohini mein kaam kar sakta hoon?" returns the correct window and a relief point.

---

## Step 12 — Civic dashboard and open platform (Expand / Design only)

**Goal:** Show the city-scale value and that the data is reusable.

- [ ] Civic page: choropleth of the grid by hazard, report volume, cells with red risk and no relief point within 1 km.
- [ ] Public read API keys via Cognito; rate limited; a one-page docs site.
- [ ] Daily export: Step Functions final state writes a CSV of risk per cell per hour to a public S3 prefix.
- [ ] OpenSearch for free-text search over reports and relief points (only if Step 8 has real volume; otherwise design only).
- [ ] Second-city proof: add `data/cities/mumbai.json` with 10 cells and show the pipeline run unchanged.

**Done when:** the civic page renders for Delhi, and a second city file produces data with no code change.

---

## Step 13 — Hardening (Core)

**Goal:** It does not fall over during judging.

- [ ] Error states in the frontend: API down, no data for cell, geolocation refused.
- [ ] Load test `GET /risk` with 200 concurrent requests; confirm CloudFront absorbs it.
- [ ] Alarm on state machine failure → email to the team.
- [ ] Freeze features. Only bug fixes after this point.
- [ ] README: problem, architecture diagram, how to run locally, how to deploy, how to add a city.

**Done when:** the "definition of done" loop (pick locality → see risk → subscribe → receive alert) works three times in a row without intervention.

---

## Step 14 — Demo video (Core)

**Goal:** The only thing the judges actually see.

- [ ] Script (3 minutes, timed):
  - 0:00–0:30 — A rider in Delhi at 1 PM, 44°C, 60% humidity. The official city-wide alert. What it does not tell him.
  - 0:30–1:30 — Chhaanv: pick Rohini, heavy work, see the red block, the safe-window sentence, the water point 200 m away. Switch to the Waterlogging tab.
  - 1:30–2:15 — Architecture in one diagram: Open-Meteo → Step Functions → DynamoDB → API → Amplify; SQS → SNS alerts; reports → S3. Show the real Step Functions console and the CloudWatch dashboard.
  - 2:15–2:45 — Alert arriving on a phone; supervisor view; the Hindi chatbot answering one question.
  - 2:45–3:00 — What it would take to cover every Indian city: one JSON file.
- [ ] Record screen and phone separately; rehearse twice; cut on a real timeline, not live.
- [ ] Upload, link in submission.

**Done when:** the video is under 3:00, every claim in it is something that actually runs, and someone outside the team understands the problem in the first 30 seconds.

---

## Step 15 — Blog and submission (Core)

**Goal:** Get the submission in, and a shot at the blog prize.

- [ ] Builder Center blog: the problem, why WBGT and not temperature, the single-table DynamoDB design, what fought back (Open-Meteo rate limits, Step Functions Map concurrency, Hindi string lengths breaking the layout), what you would do with a week.
- [ ] Submission form: repo link, deployed URL, video link, blog link, team members, track = Heat and Water, AWS services used (list them honestly).
- [ ] Final check that the deployed URL still works after the last deploy.

**Done when:** the submission confirmation is in the team leader's inbox.

---

## Dependency map

```
0 → 1 → 3 → 4 → 5 → 6 → 7 → 13 → 14 → 15
      ↘ 2 ↗           ↘ 8 → 9
                       ↘ 10
                       ↘ 11
                       ↘ 12
```

Steps 8–12 can run in parallel once Step 7 is done, one person per step. If anything in 8–12 is not working by the time Step 13 begins, it becomes a "designed, not built" slide in the video.

---

## AWS services, with the reason each is there

| Service | Why |
|---|---|
| Lambda, API Gateway | Every backend function |
| Step Functions | Hourly pipeline as a visible, retryable workflow |
| EventBridge | Hourly schedule |
| DynamoDB | Risk, subscriptions, reports |
| S3 | Grid files, photos, daily exports, share cards |
| SQS | Buffer between risk transitions and alert sending |
| SNS | Alert delivery (email) |
| CloudFront | Caching the API and serving share cards |
| CloudWatch | Dashboard and alarms |
| Amplify Hosting | Frontend |
| Cognito | Supervisor, school, civic sign-in and API keys |
| Cedar (open source) | Role permissions |
| Strands Agents SDK (open source) | Hindi/English assistant |
| SAM CLI, LocalStack (open source) | Local build before any cloud spend |
| OpenSearch (open source) | Report search, only if report volume justifies it |

Not used: EC2, Lightsail, App Runner, EKS/ECS/Fargate, SageMaker. Nothing in this project needs a server or a cluster, and there is no training data for a model.
