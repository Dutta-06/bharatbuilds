# Submit a job

The Submit page turns a job description into a placement. Most fields have a sensible default.

## Job

| Field | What it means | Limits |
|---|---|---|
| **Name** | A label for the queue. Optional. | Up to 80 characters |
| **GPU-hours** | Total work, such as 8 GPUs for 2 hours is 16 GPU-hours. | 0.01 to 10,000 |
| **GPUs in parallel** | How many GPUs run at once. Sets how many hours the job occupies, which is GPU-hours ÷ GPUs rounded up. | 1 to 1,024 |
| **GPU type** | A100, H100, L4, T4 or V100. Sets the power the job draws. | |

## Timing

**Finish within** is how many hours from now the job must be done. The preset buttons are 6, 12, 24, 48 and 72 hours. More time gives the scheduler more candidate hours, which usually means a bigger saving. Deadlines can be up to 720 hours (30 days).

## Priorities

- **Optimise for** sets the balance between water and carbon, in steps of 10%.
- **Compare savings against** is the region you would run the job in today, starting now. Every saving is measured against that. It is not a constraint on where the job can run.

## Constraints

- **Data residency** limits the job to regions in the same jurisdiction as the comparison region: India, the EU, the US or Singapore.
- **Limit regions** (under Advanced) restricts the job to the regions you tick.
- **Checkpointable** (under Advanced) also shows the best plan if the job were split into up to 6 chunks across regions and hours. The split plan is advice only. The job still runs as a single block.

## The estimate panel

While you fill in the form, the panel on the right prices the job against the live 48-hour forecast and names the best region and hour that fits your deadline and constraints. It uses the same data as the [Surface](#/docs/guide-surface). It is an estimate. Placement checks every candidate and writes the final plan.

If the deadline is shorter than the job needs, the panel says so before you submit.

## After you press Place job

You land on the job page. See [Queue and jobs](#/docs/guide-queue) for what happens next.

## Teams

If your job names a team (through the API), the team's [policy](#/docs/guide-policies) sets the weights and may restrict regions. The page itself does not set a team.
