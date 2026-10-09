# Team policies

Policies let a platform lead set how a team's jobs are placed, whatever the person submitting chooses.

## What a policy sets

- **Water and carbon weights** for the team.
- Optionally **allowed regions**, **data residency** and **max delay**.

A job that names its team (`"team": "ml"` through the API) is placed under that team's policy:

- the team's weights **replace** the job's own weights;
- the job may **narrow** the allowed regions but never widen them.

A job that names a team with no policy is rejected with an error. Jobs with no team are unaffected.

## Signing in

The **Policies** page needs a sign-in. Reading a policy needs any signed-in user. **Saving** needs membership of the `platform-leads` group. Self sign-up is turned off, so an administrator creates each user.

## Setting a policy

1. Sign in on the Policies page.
2. Enter a team name and press **Load**. If the team has no policy yet, saving creates one.
3. Move **Optimise for** to the balance you want.
4. Press **Save policy**. The next job for that team uses it.

The page currently edits the water and carbon weights. Other fields can be set through the [API](#/docs/api).

## Checking that it worked

Submit a job with the team name, then open the job. Its request shows the weights that were applied. A policy that sets 100% water shows a water weight of 1.0 on the job whatever was submitted.
