# How Tidewise prices a GPU-hour in water and carbon

One page, for anyone on the team who has to explain this to a judge. Every
number below lives in [`model/coefficients.yaml`](../model/coefficients.yaml)
with its source.

## The formula

For a job needing `E_it` kWh of IT energy, in region `r` at hour `h`:

```
E_facility = E_it × PUE(r)
litres     = E_it × WUE_site(r,h)  +  E_facility × WUE_grid(r,h)
kg CO2     = E_facility × CI(r,h) / 1000
cost       = w_water × litres × S(r)  +  w_carbon × kg
```

WUE (water usage effectiveness) is defined per kWh of **IT** energy, so on-site
water uses `E_it`. The power plant supplies the whole facility, including
cooling overhead, so grid water and carbon use `E_facility`. This is the one
place we deviate from the plan's shorter formula.

Costs are normally shown relative to "run now, in the submit region" = 1.0, so
weights are unitless (0.5 / 0.5 means "care equally").

## 1. Energy (`model/energy.py`)

`E_it = GPU-hours × GPU board power × 0.7 utilisation × 1.3 server overhead`.
For example, 4 A100-hours is 4 × 0.4 kW × 0.7 × 1.3 = 1.46 kWh. After the job runs, the
measured kWh replaces this estimate and every number in the receipt rescales.

## 2. Wet-bulb (`model/wetbulb.py`)

Wet-bulb is the lowest temperature evaporation can reach, and it is what cooling
towers chase. We solve the WMO psychrometric equation with surface pressure, so
it is right at altitude. Stull (2011) is kept as a sea-level cross-check.

## 3. On-site water: `WUE_site` (`model/water.py`)

Physics sets the **shape** over the day. Disclosure sets the **level**.

| Cooling | When it uses water | How much |
|---|---|---|
| tower (chillers + cooling towers) | wet-bulb above 10 °C, fully above 18 °C | heat (1.2 kWh per IT kWh) ÷ latent heat (2.43 MJ/kg) × 5/4 for blowdown ≈ **2.2 L/kWh** at full load |
| hybrid | like tower, but 5 °C warmer before it starts | same plateau |
| adiabatic (direct evaporative air) | outside air above 27 °C | water to cool server airflow down to 27 °C (never below wet-bulb), about **0.14 L/kWh per °C** above setpoint |
| air | never | 0 |

Real facilities mix designs and setpoints, so each region's curve is scaled so
that its yearly average equals what AWS discloses for that region
(`scripts/calibrate_wue.py`). For example, Singapore discloses 1.68 L/kWh. Its wet-bulb sits at
25-27 °C all year, which puts the tower curve on its 2.2 plateau, so the scale
is about 0.76.

## 4. Grid water: `WUE_grid`

Power plants evaporate water too. We take the generation mix for that hour and
weight NREL's median consumption per source (Macknick et al. 2012): coal 2.6,
nuclear 2.5, gas 0.75, solar ~0, wind 0 L/kWh. Hydro reservoirs evaporate a lot
(~17 L/kWh), but that water serves irrigation and supply as well. Hydro is
**excluded by default**, which is a stated choice.

This is why water and carbon can disagree. Nuclear is low-carbon but thirsty,
and a cool night in a coal-heavy grid can still be wet. The scheduler weighs
them as you ask.

## 5. Carbon: `CI`

gCO2 per kWh consumed, from Electricity Maps by zone (life-cycle,
consumption-based).

## 6. Water stress: `S(r)`

`S = 1 + Aqueduct baseline water stress / 5`, from 1.0 (plenty) to 2.0
(extremely stressed). A litre taken in Hyderabad costs more than one in Stockholm.

## Uncertainty

Each coefficient carries a ± band. Receipts show low-high ranges for litres and
kg, combined in quadrature. Absolute litres are uncertain (±40-60% before
calibration). The **ranking** of slots is much more robust, because most errors
apply equally to every slot. That ranking is all the scheduler needs.

## Limitations (say these out loud)

- We control no facility. Cooling water is modelled from published curves,
  calibrated to operator-disclosed annual WUE.
- Grid water uses US median factors per source, applied globally.
- AWS does not publish facility locations or per-site cooling designs. We use
  the region's metro area and an assumed design.
- Only deadline-flexible jobs benefit.
