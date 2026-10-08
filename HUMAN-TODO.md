# Things only a human can do

The build environment has no access to Open-Meteo, Electricity Maps, AWS or most
source websites, so these are left for the team. Tick them off here (edit the
file in a PR) so everyone can see what's done.

## Accounts and keys (Step 0)
- [ ] Every member verifies student status on AWS Builder Center.
- [ ] Team leader checks in on the hackathon page.
- [ ] Team AWS account: MFA on root, an IAM user per member, billing alarms at $5 and $20.
- [ ] Electricity Maps free API key. Then record in this file:
      - [ ] Does `carbon-intensity/forecast` work with the free key? (yes / no)
      - [ ] How many zones does the key allow? (the plan needs 8, see `data/regions.yaml`)
      - [ ] Do `carbon-intensity/history` and `power-breakdown/history` return 24 h?
      Set it locally with `export ELECTRICITYMAPS_TOKEN=...`. Never commit it.
      Result from the deployed pipeline (2026-10-08): **forecast works with the free key for all 8
      zones** (every region reports `electricitymaps-forecast`, beyond its horizon the last value
      is held and labelled `electricitymaps-latest-held`). The 24 h history endpoints are not yet
      checked; the 60-day carbon history still has to build up before `train_forecasts.py` can
      train a carbon model.

## Cost model (Step 1)
- [ ] Open each `source.url` in `model/coefficients.yaml`, confirm the number and set
      `checked: true`. Priority: `regional_wue` (AWS CSV) and `grid_water_factors`
      (NREL paper, Table 1; one search summary gave coal 479 / gas 205 gal/MWh,
      where we use 687 / 198).
- [ ] `python scripts/calibrate_wue.py`, then commit the `wue_scale` values it writes to
      `data/regions.yaml`.
- [ ] `python notebooks/wue_validation.py`. The plan requires at least 2 regions to show
      "yes". Paste the output into the notebook's last cell.

## Region data (Step 2)
- [ ] Confirm each `electricity_maps_zone` in `data/regions.yaml` against the Electricity
      Maps zone list.
- [ ] Look up WRI Aqueduct baseline water stress (0-5) for each region's basin
      (https://www.wri.org/applications/aqueduct/water-risk-atlas) and fill
      `water_stress_score`.
- [ ] `python scripts/set_water_stress.py --list` shows each region's coordinates; look the scores up in the
      Aqueduct atlas, then `python scripts/set_water_stress.py ap-south-1=<score> eu-north-1=<score> ...`
      (it validates 0-5 and keeps the file's comments), then `make validate`.
- [ ] Replace the placeholder `grid_mix` and `typical_ci_g_per_kwh` with real annual
      figures (Electricity Maps zone pages or Ember), then remove `placeholder: true`.
- [ ] `python scripts/pull_history.py --days 60`, then
      `python scripts/validate_data.py --history` must pass.
- [ ] Optional but better for the replay: download Alibaba `pai_task_table.csv`
      (https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020) and run
      `python scripts/sample_trace.py --alibaba <path> --n 500`. Until then, replay uses
      `data/trace.synthetic.csv` and must say so.

## Deploy to AWS (Step 8)
Status (2026-10-07): stack `pravaah` is deployed in ap-south-1 with `EnableCloudFront=false`,
workers are in 6 of 8 regions, `/surface` returns 8 regions and a cross-region job ran in
eu-north-1. Still open, in order:
- [ ] **CloudFront is blocked**: AWS says "Your account must be verified before you can add new
      CloudFront resources". Open an AWS Support case (Account and billing) with that error text.
      Once cleared: `sam deploy` with `EnableCloudFront=true` (the default), then use the new `ApiUrl`.
- [ ] A Lambda quota increase (concurrent executions 10 -> 1000) was requested through Service
      Quotas. The load test fails at 10 (503s) until it is granted or CloudFront caching is on.
      New accounts are often denied; if so, ask in the same Support case.
- [ ] **ap-south-2 (Hyderabad) is an opt-in region**: enable it in Billing -> Account -> AWS Regions,
      then `make deploy-workers`. Until then jobs placed there fall back to `inline-fallback`.
- [ ] `aws configure` with your IAM user, region `ap-south-1`.
- [ ] `make deploy`. On the guided prompts, set the stack name to `pravaah` and paste
      `ElectricityMapsToken` (or leave it empty for the labelled modelled profile).
      Put your email in `NotificationEmail`, keep `Offline=false`, and save the
      arguments to samconfig.toml.
- [ ] Confirm the SNS subscription email AWS sends you.
- [ ] `make deploy-workers` puts the worker in all 8 regions, so jobs really run in the
      chosen region. Without it, the receipt honestly says `launched_via: inline-fallback`.
- [ ] `make forecast-now`, then check that `curl <ApiUrl>/surface?gpu_hours=4` returns 8 regions.
- [ ] Submit a job with `"allowed_regions": ["eu-north-1"], "max_delay_h": 0` and check that
      the receipt shows `ran_in: eu-north-1` and `launched_via: cross-region-lambda`.

## Dashboard (Step 9)
- [ ] In Amplify, also set `VITE_SURFACE_URL` to the stack output `SurfaceUrl`. The standard
      views then load from S3 (static files refreshed hourly) and bursts never reach Lambda;
      custom weights still use the API.
- [ ] Amplify Hosting: connect the GitHub repo, pick the `main` branch. `amplify.yml` handles
      the build. Set the environment variable `VITE_API_URL` to the stack's `ApiUrl` output.
- [ ] Open it on an actual phone and run Lighthouse (mobile). The plan's target is above 80.
- [ ] Ask someone outside the team to submit a job and find its receipt without help
      (the plan's Step 9 "done when").

## Trace replay (Step 10)
- [ ] `make real-data` (laptop or Colab, needs internet; `export ELECTRICITYMAPS_TOKEN=...` for real
      carbon) pulls 60 days of history, validates it, reruns the replay and prints what it used. For real
      carbon over more than the last 24 h, first `aws s3 sync s3://<BucketName>/history data/history`:
      the deployed `collect_history` Lambda has been saving real hours since deploy day. Add
      `REPLAY_ARGS="--trace data/trace.alibaba.csv"` once the real trace is sampled. Commit
      `dashboard/public/replay.json`. The shipped file uses
      **synthetic weather, modelled carbon and a synthetic trace**, and says so on the page.
      Do not quote its numbers in the video or blog until it has been rerun on real data.
- [ ] Note for the blog: in the synthetic run, shifting time alone saves ~0% water (hot regions
      sit on the cooling-tower plateau all day, cool ones barely evaporate) but ~8% CO2. Moving
      region drives most of the savings. Check whether real hourly weather changes this.

## Forecast models (Step 4)
- [ ] The deployed `collect_history` Lambda (every 6 h) saves real carbon + weather hours to
      `s3://<BucketName>/history/<region>.csv`. After about 10 days, `aws s3 sync s3://<BucketName>/history
      data/history`, then (Colab is fine) `python scripts/train_forecasts.py --days 60`. It writes `forecasting/models/*.json`
      only for models that beat both persistence and the provider on the last 7 days, plus
      `metrics.json` with every verdict. Commit them and redeploy; `predict` picks them up.
- [ ] For the video and blog, quote `forecasting/models/metrics.json` honestly, including
      regions where the model was **not** used ("forecast models that didn't beat persistence
      at first" is one of the plan's blog topics).
- [ ] Training can run anywhere (e.g. Google Colab): `pip install scikit-learn pyyaml`, then
      `python scripts/train_forecasts.py --days 60`, commit the `forecasting/models/*.json` it writes and redeploy.
      SageMaker is not used, so leave it out of the submission's services list.

## Hardening (Step 14)
- [ ] After deploy: `python scripts/load_test.py <ApiUrl>/surface?gpu_hours=4` (200 concurrent).
      Expect 0 errors and mostly `x-cache: Hit from cloudfront`.
- [x] Checked: the CloudFront origin request policy id in `template.yaml`
      (`b689b0a8-...`, the managed "AllViewerExceptHostHeader"). If the deploy rejects it,
      look it up in the CloudFront console → Policies → Origin request.
- [ ] Freeze features. Then run the definition-of-done loop three times in a row without
      touching anything: submit 1 GPU-hour with a 24 h deadline → watch the placement → job
      runs in another region → receipt with measured CPU energy.

## Video and blog (Steps 15-16)
- [ ] Record from `docs/video-script.md` once the stack is deployed and the replay has been
      rerun on real data. Replace every [bracket].
- [ ] Finish `docs/blog-draft.md` with real numbers and post it on Builder Center.
- [ ] Submission form: repo, deployed URL, video, blog, track = Heat and Water, services used
      (the template's real list: Lambda, API Gateway, Step Functions, EventBridge, DynamoDB,
      S3, SNS, CloudFront, CloudWatch, Amplify; SageMaker only if you ran training there).

## Policies, sign-in and the public API (Step 12)
- [ ] Create a platform lead (self-sign-up is off):
      `aws cognito-idp admin-create-user --user-pool-id <UserPoolId> --username you@example.com`
      then `aws cognito-idp admin-set-user-password --user-pool-id <UserPoolId> --username you@example.com --password '<Strong1Password>' --permanent`
      and `aws cognito-idp admin-add-user-to-group --user-pool-id <UserPoolId> --username you@example.com --group-name platform-leads`.
- [ ] In Amplify, set `VITE_COGNITO_CLIENT_ID` (output `UserPoolClientId`) and `VITE_COGNITO_REGION`.
      The Policies page was **not** tested against a real user pool. Try it once.
- [ ] Plan check: sign in, set team `ml` to 100% water, submit a job with `"team": "ml"`, and
      confirm the job's `request.weights` shows water 1.0.
- [ ] `/price` has throttling but no API keys (HTTP APIs don't support them; see docs/api.md).

## Assistant (Step 13)
- [ ] Choose how the assistant reaches its model:
      - **Open model via an OpenAI-compatible API (Qwen, Kimi, ...):** deploy with
        `AssistantProvider=openai`, `LlmBaseUrl` (e.g. `https://openrouter.ai/api/v1`),
        `LlmModelId` (the provider's model name) and `LlmApiKey`. `LlmApiKey` may hold several keys
        separated by commas (e.g. one per team member); when one is rate-limited the next is tried. The model must support tool
        calling; run `make assistant-eval` to see whether it reaches 16/20 and tune
        `SYSTEM_PROMPT` if not.
      - **Anthropic API:** deploy with `AssistantProvider=anthropic` and `AnthropicApiKey=<key>`.
        For anything beyond the hackathon, move the key to Secrets Manager.
      - **Amazon Bedrock:** enable Claude Opus 5.5 model access in the Bedrock console, then deploy
        with `AssistantProvider=bedrock` and `BedrockModelId` set to the model or inference-profile
        id the console shows for your region.
- [ ] Run the plan's test (costs model tokens: 20 short agent turns against a local stub API, so
      no real jobs are created): `pip install -r requirements-assistant.txt`, then
      `ANTHROPIC_API_KEY=... make assistant-eval`. The plan requires **16 of 20**. Failures print
      the reason and the reply. Tune `SYSTEM_PROMPT` in `assistant/agent.py`, not the test set.
- [ ] Plan check: "run this 8-GPU-hour job by Friday with least water" on the Assistant page
      submits a job with weights water 1 / carbon 0 and a Friday deadline.
