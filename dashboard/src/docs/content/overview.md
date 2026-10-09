# What Tidewise does

Tidewise decides **where and when** to run an AI job so it uses the least cooling water and the cleanest electricity, without missing your deadline. It then gives you a receipt that shows what the choice saved.

## Why this matters

Training, fine-tuning, batch inference and evaluation sweeps usually have deadlines in hours or days. That slack is a free lever. Two things change a lot from one place and hour to the next:

- **Cooling water.** Data centres cool servers by evaporating water when the air is warm and humid, and they use little when it is cool and dry. The same job can need several times more water in Mumbai at 3 pm than in Stockholm at 3 am.
- **Carbon.** The electricity that powers the job is cleaner at some hours and in some regions, for example when wind and hydro dominate.

Most scheduling tools only look at carbon. Tidewise weighs water and carbon together, and you choose how much each one matters.

## How it works in five steps

1. **You submit a job.** You say how many GPU-hours it needs and by when it must be done.
2. **Tidewise checks the next 48 hours.** Every hour it refreshes a forecast of weather and grid carbon for each region, then prices your job in every region and hour that still meets the deadline.
3. **It picks the cheapest slot** and explains the choice in plain language, including what the alternatives would have cost.
4. **The job waits and runs.** It starts at the chosen hour in the chosen region.
5. **You get a receipt.** It shows litres of water and kilograms of CO₂, compared with running the same job right away in the region you submitted from.

## What you get

| You see | Where |
|---|---|
| The best region and hour for a job, before you commit | [Submit](#/docs/guide-submit) |
| The cost of every region and hour for the next 48 hours | [Surface](#/docs/guide-surface) |
| Where every job runs and what it saves | [Queue](#/docs/guide-queue) |
| A shareable, printable record of one job | [Receipts](#/docs/receipts) |
| Savings over time, by team | [Savings](#/docs/guide-savings) |
| Per-team water and carbon priorities | [Team policies](#/docs/guide-policies) |
| Plain-language scheduling | [Assistant](#/docs/guide-assistant) |

## What Tidewise is not

- **It does not run your training code.** In this deployment a small stand-in workload runs in the chosen region, so that placement, the cross-region launch and a measured energy reading are all real. Your job's own energy in the receipt is estimated from GPU-hours. See [Receipts](#/docs/receipts).
- **The water and carbon figures are estimates.** They come from published cooling curves and grid data, shown with ranges. The ranking of slots is more reliable than the absolute litres. See [Water and carbon](#/docs/water-and-carbon) and [Limits](#/docs/limits).
- **It cannot help with jobs that must start now.** The savings come from flexibility in time and place.

> **Start here:** the [quickstart](#/docs/quickstart) takes about two minutes.
