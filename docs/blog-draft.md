# Builder Center blog: draft

Working title: **Tidewise: scheduling AI jobs for less water, not just less carbon**

Topics follow plan Step 16. Replace every [bracket] with numbers from real runs.

## The problem
- Evaporative cooling: water per kWh rises steeply with outdoor wet-bulb.
- Grid electricity carries its own water (coal and nuclear plants evaporate litres per kWh).
- Carbon-aware schedulers exist (Carbon Aware SDK, KEDA's carbon-aware scaler). Nobody
  schedules for water. Tidewise does both.

## Why wet-bulb, not temperature
- A cooling tower can only cool towards wet-bulb, so the physics curve is
  `share_evaporative(T_wb) × heat × 3.6 / 2.43 × C/(C-1)`, which plateaus near 2.2 L/kWh.
- We solve the WMO psychrometric equation with surface pressure, not the Stull fit.
  Stull assumes sea level, and Hyderabad sits at 950 hPa.
- Physics gives the shape; AWS's disclosed per-region WUE gives the level (calibration).

## The cost model, with every number sourced
- `coefficients.yaml`: every coefficient has a source, an uncertainty and a `checked` flag.
- IT energy vs facility energy: WUE is per IT kWh, while grid water and carbon apply to IT × PUE.
- Uncertainty bands on every receipt. Absolute litres are ±[40-60]%, but the ranking holds.

## Why the water and carbon optima differ
- Nuclear: [2.5] L/kWh but near-zero carbon. Gas: [0.75] L/kWh but [400+] g/kWh.
- Hydro reservoir evaporation is excluded by default. Including it flips some regions.
- Replay: water-only weights save [85]% water / [71]% CO2; carbon-only weights save [46]% / [90]%.

## The single-table DynamoDB design
- `FORECAST#<region>` / `HOUR#<utc>`, `JOB#<id>`, `RECEIPT#<id>`, and GSI1 for the queue.
- Costs computed on read, so a coefficient change needs no backfill.

## What fought back
- **Zone mapping:** AWS regions to Electricity Maps zones, and the free tier's single-zone /
  24 h limits ([what we found]).
- **Cross-region launch:** per-region workers, IAM for `lambda:InvokeFunction` across regions,
  and an inline fallback that tells the truth about where the work ran.
- **Forecast models:** they didn't beat persistence at first ([metrics.json]).
- **Step Functions Local** didn't accept the newer `ItemProcessor` Map syntax.
- **No GPUs on Lambda or Fargate:** the receipt separates the declared job from the proxy workload.

## Results
- Replay: [table] (real trace, real history, with the perfect-foresight caveat).
- Live: [N] jobs placed during the event, [litres] saved (modelled).

## Limitations
- No facility is controlled; cooling water is modelled; grid water factors are US medians.
- Only deadline-flexible work benefits.

## With another week
- Splittable jobs (OR-Tools), facility-level simulation (OpenDC), provider WUE ingestion,
  a Kubernetes scheduler plugin.
