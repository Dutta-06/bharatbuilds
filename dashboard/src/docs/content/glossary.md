# Glossary

**Alternative.** The best placement in another region, shown beside the chosen one so you can see what you would give up.

**Baseline.** The reference for comparison: running the job immediately in the region you submitted from.

**Carbon intensity (CI).** Grams of CO₂ emitted per kWh of electricity from the grid at that place and hour.

**Cost index.** The combined water and carbon cost of a placement, relative to the baseline. 1.0 means the same as the baseline. 0.6 means 40% lower.

**Cooling tower.** Cooling equipment that evaporates water to reject heat. Used in the model for hot, humid regions.

**Data residency.** A constraint that keeps a job in the legal jurisdiction of its submit region.

**Deadline.** The time by which the job must finish.

**Forecast run.** One refresh of the weather and carbon forecasts, hourly. The header shows when it last ran.

**GPU-hours.** GPUs multiplied by hours of use. Eight GPUs for three hours is 24 GPU-hours.

**Grid water.** Water used to generate the electricity that powers the job, mainly in thermal power plants.

**Max delay.** The longest a job may wait before starting.

**Nudge.** An email saying a waiting job could now be placed at least 15% better.

**Placement.** The chosen region and start hour.

**Policy.** Team-wide rules for weights, regions, residency and delay.

**Receipt.** The record of a job's placement and the water and carbon it saved.

**Reschedule.** Moving a waiting job to a better slot using the newest forecast.

**Site water.** Water evaporated on site to cool the servers.

**Surface.** The grid of cost by region and hour.

**Water stress.** How scarce fresh water is in the area, from 0 to 5. Higher stress raises the weight of water used there.

**Weights.** How much water and carbon each matter in the cost index.

**Wet-bulb temperature.** The lowest temperature air can reach by evaporating water into it. It decides how much cooling water a site needs.

**WUE.** Water usage effectiveness, litres of water per kWh of IT energy.
