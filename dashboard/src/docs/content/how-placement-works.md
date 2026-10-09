# How placement works

## The hourly forecast

Every hour a pipeline refreshes a **48-hour grid** for each of the eight [regions](#/docs/regions). For every region and hour it holds:

- air temperature, humidity and pressure from Open-Meteo, from which it works out the **wet-bulb temperature** (the lowest temperature that evaporation can reach, and the one cooling towers are limited by);
- the grid's **carbon intensity** and generation mix from Electricity Maps.

Each row records where it came from. See [Data and forecasts](#/docs/data-and-forecasts).

## Pricing a job

For a candidate region and start hour, Tidewise estimates three things:

1. **Energy.** GPU-hours × the GPU's board power × 0.7 utilisation × 1.3 server overhead. Four A100-hours is about 1.46 kWh of IT energy.
2. **Water.** On-site cooling water (set by the wet-bulb temperature and the region's cooling design) plus the water used by the power plants that supply the electricity.
3. **Carbon.** Energy including facility overhead, times the grid's carbon intensity.

It then combines water and carbon using your weights into a single [cost index](#/docs/cost-index).

## Choosing the slot

A job runs for `ceil(GPU-hours ÷ GPUs)` whole hours in one region. The scheduler considers every region and every whole-hour start that satisfies all of these:

- the job **finishes by your deadline**;
- the start is within **max delay** if you set one;
- the region is **allowed** (all regions unless you limited them, and only the comparison region's jurisdiction if you asked for [data residency](#/docs/guide-submit));
- the forecast covers every hour of the run.

The cheapest candidate wins. If two tie, the earlier start wins, then the comparison region. The explanation also lists the best slot in each of up to three other regions, so you can see what you would have paid elsewhere.

If nothing fits, the job is marked **infeasible** and the explanation says why, for example that the job needs 6 hours but the deadline is in 4.

## After placement

| Stage | What happens |
|---|---|
| **Placed** | The plan is stored and a run is started. |
| **Waiting** | The run waits until the chosen start hour. You can ask for a better slot during this time. |
| **Running** | The job launches in the chosen region. |
| **Done** | A receipt with measured energy is stored and you are emailed. |

If the forecast changes while a job waits, Tidewise can find a better plan inside the same constraints. See [Queue and jobs](#/docs/guide-queue).

## What is checked, and what is not

The scheduler is exact for the forecast it is given. The forecast itself is uncertain, which is why receipts show ranges and why a plan can improve as new forecasts arrive.
