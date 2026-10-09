# Receipts

A receipt records what a placement saved. Each job has two stages of receipt.

## Preview and final

| | Preview | Final |
|---|---|---|
| **When** | The moment the job is placed | After the job has run |
| **Based on** | Forecasts at placement time and an energy **estimate** | The same plan, with the **measured** energy of the stand-in workload |
| **Where** | Job page, marked "modelled preview" | Job page and the share page, with where the job ran |

Until a job has run, the receipt API returns status `202` with the preview. Once it has run, it returns `200` with the final receipt.

## What a receipt contains

- **Water** and **carbon** for the chosen slot, each with a low to high range.
- The same figures for the **baseline**: running immediately in the comparison region.
- The **saving** as a percentage for each.
- **Where the job ran**, which region you requested, and how it was launched.
- The **stand-in run**: wall time, CPU time, epochs and measured energy.

## What is measured and what is modelled

This distinction matters when you quote a receipt.

- **Measured:** the energy used by the small CPU workload that runs in the chosen region. It is CPU time multiplied by a per-vCPU power figure.
- **Modelled:** everything about your job. Its energy is estimated from GPU-hours and board power. The water and carbon for both the chosen slot and the baseline are computed from forecasts and published factors.

Tidewise does not run your actual GPU work, so no GPU energy is measured. The receipt says this in plain words under **Stand-in run**.

## The stand-in workload

A short CPU training loop runs in the region the scheduler chose, launched by a function in that region. It shows that a placement is really executed there, and it provides a real energy reading for the receipt. If a region has no worker deployed, the job runs in the main region and the receipt says `inline-fallback` with the reason.

## Sharing and exporting

On a job page, open **Share, export or print**. The receipt page offers:

- **Copy link.** Anyone with the link can see the receipt. Job IDs are random, but there is no sign-in on receipts.
- **Download JSON** for the full record.
- **Download CSV** for a flat table of the same facts.
- **Print or save as PDF** from the browser. The page is formatted for paper.

## Reading the numbers

- Use the **percentage saving** and the **ranking** with confidence. They are the robust part.
- Quote **litres and kilograms with their range**, and say they are modelled.
- Do not add receipts together and call the total "measured".
