# The cost index

Everywhere in Tidewise you see a number called **cost**, such as `0.09` or `1.00`. It is not money.

## What it means

**Cost is relative to running now in the comparison region.**

- `1.00` means the same combined water and carbon as running right now where you submitted from.
- `0.50` means half.
- Anything above `1.00` is worse than running now.

Lower is better. The comparison region is the one you pick as **Compare savings against** on the Submit page, and it defaults to ap-south-1 (Mumbai).

## How it is calculated

```
cost = w_water × (litres × water-stress factor) + w_carbon × kg CO₂
```

each divided by the same quantity for the comparison slot, so the result is unitless. The weights come from the **Optimise for** slider:

| Slider | Water weight | Carbon weight |
|---|---|---|
| All water | 1.0 | 0.0 |
| Balanced (default) | 0.5 | 0.5 |
| All carbon | 0.0 | 1.0 |

## The water-stress factor

A litre of water is worth more where water is scarce. When a region has a water-stress score, its water is multiplied by `1 + score ÷ 5`, from 1.0 (plenty of water) to 2.0 (extremely stressed). Until a score is entered for a region the factor is 1.0.

## Why not dollars?

Tidewise measures environmental cost, not the price you pay your cloud provider. Cheaper in this sense can cost the same, or more, on your bill. Quote litres and kilograms when you talk about results, and use the index to compare slots.

## Examples

- A job priced at `0.09` in eu-north-1 uses roughly a tenth of the combined water and carbon of running now in ap-south-1.
- Cost `1.00` at your own region at the current hour is the baseline, so the baseline row always reads 1.00.
- On the [Surface](#/docs/guide-surface) page, blue cells are cheaper than the baseline, grey is about equal, and red is costlier.
