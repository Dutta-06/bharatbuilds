# Demo video

`demo.mp4` (about 2:33, 1280×720, captions burned in, no audio) is recorded automatically from the **deployed API** by
`docs/video/record.js`, so every number on screen is real and current at recording time. The competition limit is
**3:00**. Re-record any time:

```bash
cd dashboard && VITE_API_URL=<ApiUrl> VITE_COGNITO_CLIENT_ID=<UserPoolClientId> npm run build && npx vite preview --port 4173 &
API=<ApiUrl> OUT=/tmp/demo NODE_PATH=<playwright node_modules> node docs/video/record.js
python3 docs/video/finish.py /tmp/demo     # demo.mp4: typing, page loads and the assistant's wait are sped up; captions stay at reading speed
```

Recording submits one real demo job (it emails the notification address when placed and finished) and sends one real
assistant request.

## What the video shows, in order
Title · the problem with live numbers (Mumbai vs Stockholm) · Submit, with the water/carbon weights and the constraints
(data residency, allowed regions, splitting) · the 48-hour cost surface and map · placing a real job, its
plain-language explanation, reschedule/nudge and options considered · the queue · how it runs on AWS (diagram) · a
receipt with share/export · cumulative savings · forecast quality · the public price API · the assistant answering
live · team policies (sign-in) · DG-Shift Power & Operations · in-app docs · closing card.

## Not shown, and why
- **Operations scene** replays output of the real backend code as a fixture, because the live demo needs a
  `platform-leads` sign-in to reset. It is labelled simulated on screen.
- **Team policy editing** needs a signed-in platform lead; only the sign-in screen is shown.
- The CLI is not shown. **Trace replay** is not claimed; it needs the real-data run (see HUMAN-TODO.md).
- AWS console shots can't be captured from the build environment.
