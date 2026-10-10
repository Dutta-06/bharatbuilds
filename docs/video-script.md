# Demo video

`demo.mp4` (about 3:00, 1280×720, captions burned in) is recorded automatically from the **deployed API** by
`docs/video/record.js`, so every number on screen is real and current at recording time. Re-record any time:

```bash
cd dashboard && VITE_API_URL=<ApiUrl> npm run build && npx vite preview --port 4173 &
API=<ApiUrl> OUT=/tmp/demo NODE_PATH=<playwright node_modules> node docs/video/record.js
python3 docs/video/finish.py /tmp/demo        # demo.mp4 + a rescaled demo.srt
```

Recording submits one real demo job (it emails the notification address when it is placed and finishes).

## Caption script (the narration to read if you add a voice-over)
- **0:00** AI jobs need electricity, and the data centres behind them need cooling water.
- **0:08** Right now, one kWh of AI compute in Mumbai takes about 4.7 litres of water and 0.8 kg of CO₂.
- **0:15** In Stockholm: about 1 litre, and 0.02 kg. That is 5× the water and 33× the carbon.
- **0:26** Most AI work is not urgent. You tell Tidewise how much compute you need, and by when.
- **0:37** You choose how much water and carbon each matter.
- **0:42** The estimate updates live: run now in Mumbai, or wait for a better slot and region.
- **0:49** Every hour Tidewise forecasts weather and grid carbon for eight AWS regions, 48 hours ahead.
- **0:55** It prices every region and every hour. Blue is cheaper than running now in Mumbai.
- **1:03** The cheapest slot: eu-central-1, 12 Oct 2026 11:00 UTC, 88% lower cost than now.
- **1:12** The table and map show litres of water and kilograms of CO₂ for every region at that hour.
- **1:25** Place the job. Tidewise searches every region and hour that still meets the deadline.
- **1:32** It explains the choice in plain language, with the water and carbon it saves, and a range for the uncertainty.
- **1:41** Every option it considered is listed, so the choice can be audited.
- **1:46** An hourly Step Functions pipeline refreshes forecasts. Each job gets its own state machine that waits for the chosen hour…
- **1:53** …then launches in the chosen region, writes a receipt, and emails you. Forecast models are only used where they beat a naive baseline.
- **2:02** A finished job placed through the built-in assistant: it ran in Ireland instead of Mumbai.
- **2:09** Each job gets a receipt to share or print. Water and carbon are modelled; the stand-in workload's energy is measured. We say which is which.
- **2:20** Across 10 jobs placed so far: 44 litres of water and 7.8 kg of CO₂ saved, by team and over time.
- **2:29** And when the grid fails, DG-Shift protects critical services and defers flexible work while the site runs on a generator.
- **2:36** Simulated demo: 47 kW of IT demand drops to 19 kW. 42 kWh of work moves to later. Every deadline still holds.
- **2:45** Everything is documented in the app: concepts, user guide, API reference, FAQ.
- **2:49** Water and carbon are modelled, so absolute litres are uncertain. The ranking of slots holds up.

## Scenes
1. Title and the problem: live water and CO₂ per kWh, Mumbai against Stockholm (`/price`).
2. Submit: describe a job, set the water/carbon balance.
3. Surface: scrub 48 hours, find the cheapest region and hour.
4. Place a real job and read the explanation and the options considered.
5. How it runs on AWS (diagram).
6. A finished job and its receipt.
7. Savings so far (live `/savings`).
8. Power & Operations (DG-Shift). **This scene replays output of the real backend code as a fixture** because resetting the
   live demo needs a platform-leads sign-in. To show it live, sign in, press Reset demo, run the scenario, and screen-record it.
9. Docs, then the closing card.

## Not in the video, and why
- The trace replay (e.g. "500 jobs from a public GPU trace") is **not claimed**: it needs the real-data run on a machine
  with Open-Meteo access (see HUMAN-TODO.md). Add a scene with its real numbers once you have them.
- AWS console shots (Step Functions graph, CloudWatch) can't be captured from here; record them yourself and cut them
  in after the architecture slide.
- No voice-over: add your own over the captions, or leave the captions as they are.
