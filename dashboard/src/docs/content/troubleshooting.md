# Troubleshooting

## The page shows an error box

The dashboard could not reach the API. Reload the page. If it persists, check the `/health` route of your API. If you run your own deployment, check the stack in CloudFormation.

## The header says "no forecast data"

No forecast run has completed. The first run happens after deployment, and then every hour. A deployer can start one manually with `make forecast-now`.

## The header dot is amber or red

Amber means the forecast is more than 90 minutes old or carbon is modelled for some region. Red means more than 3 hours old. Placements still work from the last forecast but may be less accurate.

## The Surface page is empty

There is no forecast yet, or the request failed. See the two items above.

## My job is stuck on "waiting"

That is normal until the start hour. The job page shows the start time in your local time zone. If the time has passed and nothing happened, check the failure reason on the job page and your notification email.

## My job failed

The job page shows the reason. Common causes are a downstream service error or a permission problem in your deployment. You can submit it again.

## I never got an email

Confirm the subscription email from Amazon SNS, and check your spam folder. See [Notifications](#/docs/notifications).

## Reschedule says no better slot

The newest forecast has nothing better inside the job's constraints. That is not an error.

## I cannot save a policy

Writing needs sign-in as a member of the `platform-leads` group. Reading needs only a sign-in.

## The assistant returns an error

`503` means the language model is unavailable or rate limited. `504` means it took too long. Use the Submit page, or try again.

## Still stuck

Check the [API reference](#/docs/api) to reproduce the request directly, and keep the job id and time of the problem when you report it.
