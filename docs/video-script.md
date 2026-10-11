# Demo video

`demo.mp4` (170 s, 1280×720, captions burned in) is recorded automatically from the **deployed API** by
`docs/video/record.js`, so every number on screen is real and current at recording time. The competition limit is
**3:00**; keep the final upload under it. Re-record any time:

```bash
cd dashboard && VITE_API_URL=<ApiUrl> VITE_COGNITO_CLIENT_ID=<UserPoolClientId> npm run build && npx vite preview --port 4173 &
API=<ApiUrl> OUT=/tmp/demo NODE_PATH=<playwright node_modules> node docs/video/record.js
python3 docs/video/finish.py /tmp/demo 1.08      # demo.mp4 (8% faster, to fit 3:00) + a rescaled demo.srt
```

Recording submits one real demo job (it emails the notification address when it is placed and finishes) and sends one
real assistant request.

## Caption script
- **0:00** Tidewise decides where and when to run AI jobs, so they use the least water and carbon.
- **0:06** One kWh of AI compute right now: in Mumbai, 3.9 litres of water and 0.6 kg of CO₂.
- **0:11** In Stockholm: 1 litre and 0.02 kg. 4× the water, 26× the carbon.
- **0:18** Most AI work is not urgent. Say how much compute you need, and by when.
- **0:26** Choose how much water and carbon each matter.
- **0:31** The estimate updates live, against running now in Mumbai.
- **0:35** Hourly forecasts of weather and grid carbon for eight AWS regions, 48 hours ahead.
- **0:40** Every region and hour is priced. Blue is cheaper than running now in Mumbai.
- **0:45** Cheapest slot: eu-north-1, 86% lower cost than now.
- **0:50** Litres of water and kg of CO₂ for every region, on a table and map.
- **1:01** Place the job: every region and hour that meets the deadline is searched.
- **1:07** A plain-language explanation, with litres and kg saved and their uncertainty ranges.
- **1:11** Waiting jobs are re-checked as forecasts change: an email nudge, and a one-click move.
- **1:16** Every option considered is listed, so the choice can be audited.
- **1:21** The queue tracks every job, from placed and waiting to running and done.
- **1:25** An hourly Step Functions pipeline refreshes forecasts. Each job gets its own state machine…
- **1:30** …that waits for the chosen hour, launches in that region, writes a receipt and emails you.
- **1:36** Every job gets a receipt: modelled water and carbon saved, with a measured stand-in run.
- **1:43** Copy a link, download JSON or CSV, or print it.
- **1:48** Across 12 jobs so far: 54 litres of water and 9.3 kg of CO₂ saved, by team and over time.
- **1:54** Forecast quality is public. A learned model is used only where it beats a naive baseline.
- **2:00** Or just ask. The assistant reads the live cost surface, and can place jobs.
- **2:23** Platform leads set team rules (weights, regions, residency, delay) behind Cognito sign-in.
- **2:29** DG-Shift: when the grid fails, critical services stay up and flexible work is deferred.
- **2:34** Simulated demo: 47 kW of IT demand falls to 19 kW, and every deadline still holds.
- **2:40** Full documentation in the app: concepts, user guide, API reference, FAQ.
- **2:44** Water and carbon are modelled, so absolute litres are uncertain. The ranking of slots holds up.

## What the video shows
Problem and live numbers · Submit · 48-hour cost surface with map · placing a real job, its explanation and options ·
reschedule and nudges · the queue · how it runs on AWS (diagram) · a receipt with share/export · cumulative savings ·
forecast quality · the assistant answering live · team policies (sign-in) · DG-Shift Power & Operations · in-app docs.

## Not shown, and why
- **Operations scene** replays output of the real backend code as a fixture, because the live demo needs a
  `platform-leads` sign-in to reset. It is labelled simulated on screen.
- **Team policy editing** needs a signed-in platform lead; only the sign-in screen is shown.
- Not covered in 3 minutes: split jobs, data-residency constraints, the public `/price` API, the CLI.
- **Trace replay** is not claimed; it needs the real-data run (see HUMAN-TODO.md).
- AWS console shots can't be captured from the build environment.
