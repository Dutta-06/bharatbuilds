# Water and carbon

Every receipt reports two numbers, litres of water and kilograms of CO₂. This page explains where each comes from and how far to trust it.

## Water

A job's water has two parts.

### On-site cooling water

Data centres reject server heat to the air. How much water that takes depends on the cooling design and on the **wet-bulb temperature**, which combines heat and humidity.

| Cooling design | When it uses water | Regions |
|---|---|---|
| **Tower** (chillers and evaporative cooling towers) | No water below 10 °C wet-bulb, rising to fully evaporative above 18 °C. About 2.2 L per kWh of IT energy at full load. | Mumbai, Hyderabad, Singapore |
| **Adiabatic** (evaporative air cooling) | Only when outside air is above about 27 °C, then roughly 0.14 L/kWh for each degree above. | Stockholm, Ireland, Frankfurt, N. Virginia, Oregon |
| **Hybrid** | Like a tower, but stays dry until it is about 5 °C warmer. | None at present |
| **Air** (dry coolers) | Never. | None at present |

Physics sets the shape of the curve over the day. Each region's curve is then scaled so its yearly average matches the water use effectiveness (WUE) that AWS publishes for the region, where one exists.

### Grid water

Power stations also consume water, mostly for steam and cooling. For every hour, Tidewise takes the grid's generation mix and weights each source by its typical consumption per kWh (US medians from NREL): coal about 2.6 L/kWh, nuclear about 2.5, gas about 0.75, and solar and wind close to zero.

**Hydropower is left out by default.** Reservoirs lose a lot of water to evaporation, but that water also serves irrigation, drinking supply and flood control, and assigning all of it to electricity is contested. The effect is that hydro-heavy grids look water-light. This is a modelling choice, not a measurement.

### Why water and carbon can disagree

Nuclear power is low in carbon but uses a lot of water. A cool night on a coal-heavy grid can use little cooling water but still emit a lot of carbon. That is why you can set the balance with the slider.

## Carbon

Carbon is the energy the facility draws (IT energy times the facility overhead, PUE) multiplied by the grid's carbon intensity for that hour, in grams of CO₂ per kWh. Intensity comes from Electricity Maps and is a life-cycle, consumption-based figure for the region's grid zone.

## Uncertainty

Each coefficient has an uncertainty band, and the bands combine into the **low and high range** shown next to every figure.

- **Absolute litres are uncertain.** Treat them as the right order of magnitude, with wide ranges before a region's cooling curve is calibrated.
- **The ranking of slots is much more reliable.** Most errors apply equally to every slot, so "eu-north-1 at 2 am is much better than Mumbai at 3 pm" holds even when the litres are off.
- **Receipts after a run use measured energy** for the stand-in workload. See [Receipts](#/docs/receipts).

## Known simplifications

- AWS does not publish facility locations or cooling designs, so each region uses its metro area and an assumed design.
- Grid water factors are US medians applied worldwide.
- AWS defines WUE as water withdrawn per kWh, which is not identical to water consumed.
- Mumbai and Hyderabad have no AWS-published WUE, so they use an Asia-Pacific figure.

The full list is on the [Limits](#/docs/limits) page.
