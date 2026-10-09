# Demo video script (3:00)

Timings follow the plan (Step 15). **Every number in brackets must come from a real
run** (the deployed stack, the replay rerun on real history and the real trace, and
`forecasting/models/metrics.json`). Do not record with the synthetic numbers.
Record the screen and the AWS console separately; cut on a timeline.

## 0:00-0:30 The problem
**Visual:** a chart of water per kWh against wet-bulb (the tower curve from
`docs/cost-model.md`), then a split screen: Delhi at 3 PM (wet-bulb ~27 °C) and a
coastal or Nordic night (~8 °C).

> "Data centres cool themselves by evaporating water, and the hotter and more humid
> it is outside, the more they evaporate. In a Delhi afternoon, one kWh of AI compute
> can cost [2.2] litres of water on site, plus [2] litres at a coal plant. At night in
> Stockholm it's close to [zero] on site. The colony next door draws on the same
> stressed supply, and its peak demand falls on exactly those afternoons."

## 0:30-1:30 Tidewise in use
**Visual:** dashboard → Submit: 4 GPU-hours, deadline Friday, submitted from Mumbai.

> "Most AI work isn't urgent. Training, fine-tuning, evaluation sweeps all have
> deadlines in hours or days. Tidewise uses that slack."

**Visual:** Surface page, drag the scrubber across 48 h. Blue regions are cheaper than
"run now, here".

> "Every hour, Tidewise forecasts wet-bulb temperature and grid carbon for [8] AWS
> regions, 48 hours ahead, and prices each region-hour in litres and kilograms."

**Visual:** Job page: the explanation sentence, options considered, and the two headline
numbers with their ranges.

> "It picks the slot that finishes before the deadline with the least water and carbon,
> and tells you why: [X]% less water, [Y]% less CO2 than running now in Mumbai,
> finishing [Z] hours before the deadline."

## 1:30-2:15 How it works on AWS
**Visual:** the diagram from `docs/architecture.md`, then the real Step Functions console.

> "An EventBridge rule runs a Step Functions pipeline every hour: Open-Meteo and
> Electricity Maps in, a forecast model that's only used where it beats persistence, and
> DynamoDB out. Each job gets its own state machine. It waits until the chosen hour..."

**Visual:** the `pravaah-run` graph with the Wait state, then Launch.

> "...launches the work in the chosen region and writes the receipt."

**Visual:** the receipt: `ran_in: [eu-north-1]`, measured CPU time and energy.

> "Honest receipts: the declared GPU job's energy is estimated; the proxy workload that
> actually ran is measured. Lambda has no GPUs, and we say so."

**Visual:** the CloudWatch dashboard, briefly.

## 2:15-2:45 Does it add up?
**Visual:** Savings page, trace replay bars.

> "Replaying [500] jobs from [Alibaba's public GPU cluster trace]: [X]% less water,
> [Y]% less CO2, [100]% of deadlines met, median delay [N] hours."

**Visual:** the when-versus-where table, then the Forecast quality page.

> "Most of the saving comes from *where*, not *when*. And water and carbon don't always
> agree: a nuclear-powered grid is clean but thirsty. You set the weights."

## 2:45-3:00 Close
> "We don't control any data centre. Cooling water is modelled from published curves and
> calibrated to AWS's own disclosures, and absolute litres are uncertain. But the ranking
> of slots holds up. We used AI to decide when AI should run."

**End card:** repo URL, live URL, team names.
