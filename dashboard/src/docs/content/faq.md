# Frequently asked questions

## General

### What is Tidewise?
A scheduler that chooses the region and hour for an AI job to use the least cooling water and carbon within your deadline. See [What Tidewise does](#/docs/overview).

### Does it change my code?
No. It decides where and when the job runs and reports the result.

### Is there a cost to use it?
The dashboard does not charge for itself. It runs in the AWS account where it is deployed, so normal AWS charges for that account apply.

## Scheduling

### Why was my job delayed?
Because a later slot inside your deadline was cheaper. The job page shows the start time and the explanation. To avoid waiting, set a short **max delay**, or set the maximum delay to 0.

### Why was my job placed in another country?
You did not restrict regions. Turn on **data residency** or choose allowed regions. See [Policies](#/docs/guide-policies).

### Why is the result "infeasible"?
No region and hour met every constraint. Extend the deadline, allow more regions, or raise the max delay. The explanation names the constraint that blocked.

### Can I change a plan after submitting?
If the job is still waiting, use **Reschedule** on its page. It moves the job only if the newest forecast has a better slot. See [Queue and jobs](#/docs/guide-queue).

### What if I only care about water, or only carbon?
Move the weights. Setting water to 1 and carbon to 0 optimises water only. See [Cost index](#/docs/cost-index).

## Numbers

### Are the savings real measurements?
No. They are modelled estimates with ranges. See [Limits and accuracy](#/docs/limits).

### Why is a saving small or zero?
Sometimes the baseline already was the best slot. That is a valid result and the receipt says so.

### What does "carbon modelled" in the header mean?
Live carbon data was not available for some region, so a typical daily pattern was used. See [Data and forecasts](#/docs/data-and-forecasts).

### Why do hydro-heavy grids not count grid water?
Reservoir evaporation is hard to attribute to electricity, and counting it would distort comparisons. The default excludes it. See [Water and carbon](#/docs/water-and-carbon).

## Account and access

### Do I need to sign in?
Only to read or change team policies. Everything else is open to anyone with the URL.

### Who can change a policy?
Members of the `platform-leads` group.

### How do I get alert emails?
The notification address is set when the stack is deployed. It must confirm an email from Amazon SNS first. See [Notifications](#/docs/notifications).

## Assistant

### The assistant said it was unavailable.
The free language model it uses may be rate limited. Place the job on the **Submit** page instead, or try again later.

### Did the assistant place my job when it timed out?
It might have. Check the [Queue](#/docs/guide-queue) before asking again.
