# Notifications

Tidewise sends email through Amazon SNS to the address that was set when it was deployed. Each address must confirm the subscription once.

## Confirming

When the address is first added, AWS sends a message titled **AWS Notification - Subscription Confirmation**. Open the link in it. Until you do, no emails arrive, including alarm emails. Check spam if you do not see it.

## What you get

| Subject | When |
|---|---|
| **Tidewise: job placed** | A plan was made and the job is waiting. |
| **Tidewise: job started** | The job launched in its region. |
| **Tidewise: job finished, receipt ready** | The final receipt is available. |
| **Tidewise: job failed** | The run failed. |
| **Tidewise: job could not be placed** | No region and hour could meet the constraints. |
| **Tidewise: a better slot is available for your job** | A waiting job could be at least 15% cheaper. One email per new plan. |

Operational alarms (the forecast pipeline failing or going stale, or a job run failing) also arrive at this address.

## Better-slot emails

The email names the current plan and the better one, the saving in litres and kilograms (modelled), and a link to the job. Do nothing and the job runs as planned. Open the job and press **Move to the better slot** to switch. See [Queue and jobs](#/docs/guide-queue).

## Stopping emails

Use the **unsubscribe** link at the bottom of any message. Unsubscribing stops alarm emails as well, because they share one topic.

## Who receives them

In this version every job's emails go to the one subscribed address. There are no per-user or per-team notification settings.
