# Limits and accuracy

## Input limits

| Item | Limit |
|---|---|
| GPU-hours per job | 0.01 to 10,000 |
| GPUs | 1 to 1,024 |
| Deadline | 0.1 hours to 30 days |
| Maximum delay | 0 to 720 hours (30 days) |
| Split chunks | 1 to 6 |
| Job name | 80 characters |
| Assistant message | 2,000 characters |
| Forecast horizon | 48 hours |
| API rate | 50 requests per second, burst 100 |

Because forecasts cover 48 hours, a job with a longer deadline is still planned inside the next 48 hours.

## Supported GPUs

T4, L4, V100, A100 and H100. Energy is estimated from the board power of the GPU, an assumed utilisation and a server overhead, so a job's energy is modelled, not metered.

## How accurate are the numbers

Receipt figures are **modelled estimates**, not measurements. Each carries a low and high range that reflects the uncertainty of its inputs. Use them to compare options and to see the direction and size of a saving. Do not use them as audited reporting.

Main sources of uncertainty:

- Real cooling design and efficiency of each AWS site are not public.
- Grid water factors come from published studies and vary by plant.
- Carbon intensity is forecast, and forecasts are less certain further ahead.
- Some data can fall back to a typical value when live data is missing. Pages mark this.

## What Tidewise does not do

- It does not run your workload code. It plans the placement and starts the run.
- It does not guarantee a start time if you reschedule or if forecasts change.
- It does not measure real water use at the data centre.
