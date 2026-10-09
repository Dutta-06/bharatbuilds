# Assistant

The **Assistant** page lets you describe a job in plain language. It reads the live cost surface and can place a job for you.

## Examples

- "Run this 8-GPU-hour job by Friday with least water."
- "Where would 2 GPU-hours be cheapest tonight?"
- "Keep a 4 GPU-hour job in India and finish within 12 hours."
- "How much did job ab12cd34ef56 save?"

The example buttons on the page send the first few for you.

## What it can do

| Request | What it does |
|---|---|
| A question about cost, region or time | Reads the cost surface and answers. It does not place anything. |
| A request to run or schedule a job | Converts dates, weights and region limits into a job and places it. |
| A question about a job | Fetches its receipt. |

It assumes **IST** for times you give without a zone, and it asks one short question if the amount of work or the deadline is missing.

## What to check

- **It says what it did.** If it placed a job, the reply says so and links to the [Queue](#/docs/guide-queue). Check the job page for the actual plan.
- **Say whether you want a job run or only priced.** It only submits when you ask it to run or schedule something.
- **Costs are an index, not money.** The assistant reports litres of water and kilograms of CO₂. See the [cost index](#/docs/cost-index).
- **Language models make mistakes.** For anything that matters, confirm the region and start time on the job page.

## Limits

- Each question stands alone. It does not remember earlier messages.
- It uses a free language model, which can be slow. If an answer takes longer than about 24 seconds you get a message saying so. The page retries once automatically when it is safe, meaning when no job could have been placed. If a job might already have been placed, check the Queue before asking again.
- The free model service has a daily allowance. If it is used up, you get a message saying the assistant is unavailable, and the Submit page still works.
- Messages can be up to 2,000 characters.
