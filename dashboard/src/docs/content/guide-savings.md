# Savings

The **Savings** page adds up what placement has saved. Everything on it is **modelled**: each job's chosen slot compared with running it immediately in the region it was submitted from.

## Over time

The top of the page covers the last 30 days:

- **Water saved** and **carbon saved**, summed over jobs;
- **Jobs placed**, and how many of them have run;
- a line chart of **cumulative water saved** by day. Hover to see the total on any day. **Show as table** gives the same numbers in a table.

## By team

The table lists each team's jobs and savings. Select a team to filter the totals and the chart, and select it again to clear. Jobs submitted without a team count as `unassigned`.

## Trace replay

Below that, the page shows a **replay** of a larger set of jobs run through the scheduler two ways: every job started immediately where it was submitted, and every job placed by Tidewise. It reports water and carbon for the whole queue, the share of deadlines met, the median delay, and how many jobs moved region. It also shows:

- **When versus where:** how much comes from shifting time alone, and how much more from also changing region;
- **Deadline slack:** how savings change as deadlines get looser;
- **Optimising for:** how savings change with the water and carbon weights.

Read the assumptions box above the replay before quoting any number. It states whether the weather, carbon and job trace are real or synthetic, and that the scheduler sees the actual weather in the replay (an upper bound on what real forecasts can achieve).
