# Pravaah

Water- and carbon-aware scheduling for AI workloads. AI jobs are flexible in
time and place. Pravaah runs them where cooling needs the least water and the
grid is cleanest, without missing a deadline, and issues a receipt for what was
saved.

Environmental Hacks (Bharat Builds Tour), Heat and Water track. Plan:
[`pravaah-project.md`](pravaah-project.md). How a GPU-hour is priced:
[`docs/cost-model.md`](docs/cost-model.md).

## Status

| Step | State |
|---|---|
| 0 Setup | Repo and CI. AWS account, Electricity Maps key and eligibility are on the team |
| 1 Cost model | Library, coefficients with sources, CLI, tests, validation notebook. Sources still need a human check (`checked: false`), and the validation notebook needs a run with internet access |
| 2+ | Not started |

## Cost model

```bash
pip install -r requirements-dev.txt
make ci                                   # tests, config validation, CLI smoke test

# live weather from Open-Meteo (hours are UTC)
python -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4
python -m model --region ap-south-1 --hour 2026-10-10T09:00 --gpu-hours 4 --compare

# offline
python -m model --region eu-north-1 --hour 2026-10-10T02:00 --gpu-hours 4 --temp 8 --rh 85 --ci 35

python scripts/calibrate_wue.py           # scale site-WUE curves to AWS disclosures (needs internet)
python notebooks/wue_validation.py        # uncalibrated curves vs published WUE (needs internet)
```

## Layout

```
model/
  coefficients.yaml   every number, with source, uncertainty and a checked flag
  wetbulb.py          psychrometric wet-bulb (pressure-aware); Stull cross-check
  water.py            on-site WUE curves by cooling type, calibration, grid water
  energy.py           job energy from GPU type and hours
  cost.py             footprint, cost, receipt (with uncertainty bands)
  regions.py          loads data/regions.yaml
  openmeteo.py        weather for one hour, and history
data/regions.yaml     candidate AWS regions
scripts/              validate_data, calibrate_wue
notebooks/            wue_validation (percent-format notebook)
docs/cost-model.md    one-page explainer
```
