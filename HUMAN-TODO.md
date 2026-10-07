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
- [ ] Replace the placeholder `grid_mix` and `typical_ci_g_per_kwh` with real annual
      figures (Electricity Maps zone pages or Ember), then remove `placeholder: true`.
- [ ] `python scripts/pull_history.py --days 60`, then
      `python scripts/validate_data.py --history` must pass.
- [ ] Optional but better for the replay: download Alibaba `pai_task_table.csv`
      (https://github.com/alibaba/clusterdata/tree/master/cluster-trace-gpu-v2020) and run
      `python scripts/sample_trace.py --alibaba <path> --n 500`. Until then, replay uses
      `data/trace.synthetic.csv` and must say so.

## Deploy to AWS (Step 8)
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
