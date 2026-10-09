# Queue and jobs

## The queue

The **Queue** page lists every job, newest first, and refreshes every 10 seconds. Each row shows the status, GPU-hours, the route (comparison region to chosen region), the start time in your local time, and the water and carbon saved. Use the filter buttons to show only waiting, running, done or failed jobs. On a phone each job is a card.

## Job status

| Status | Meaning |
|---|---|
| **placed** | A plan exists and the run is being started. This is brief. |
| **waiting** | Scheduled for a later hour. The start time is on the job page. |
| **running** | Launched in the chosen region. |
| **done** | Finished. The final [receipt](#/docs/receipts) is ready. |
| **failed** | The run failed. The job page shows the reason, and you get an email. |
| **infeasible** | No region and hour could meet your constraints. The job was not run. The explanation says what to change, such as a longer deadline. |

## The job page

Open any job to see:

- the **verdict**, which explains the choice and what it saves;
- a **progress strip** showing where the job is;
- **water and carbon** with ranges, against running now at the comparison region;
- the **options considered**: the chosen slot, running now in the comparison region, and the best slot in up to three other regions;
- an optional **split plan** if you asked for one;
- the **receipt**.

Times are shown in your local time zone. Hover a start time to see it in UTC.

## Moving a waiting job

Forecasts are rebuilt every hour, so the best window can change while a job waits. On a waiting job, **Move to the better slot** looks again, using the newest forecast and your job's original constraints:

- the same allowed regions and residency rule;
- the same deadline;
- whatever remains of your max delay.

If a window at least 2% cheaper exists, the old run is stopped and a new run starts at the better window. If the old run cannot be stopped, nothing changes, so a job is never run twice. If nothing better exists, the page says so.

You cannot move a job that is already running, done or failed.

## Better-slot emails

After every hourly forecast, Tidewise checks the jobs that are still waiting. If a new plan would be at least 15% cheaper than the current one, it sends one email describing the new plan and its saving. It sends one email per new plan, not one every hour. Nothing moves until you press the button. See [Notifications](#/docs/notifications).

## Cancelling

There is no cancel button in this version. A waiting job that you no longer need will run at its start time.
