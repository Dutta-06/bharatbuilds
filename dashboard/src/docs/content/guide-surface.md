# Read the cost surface

The **Surface** page shows the [cost index](#/docs/cost-index) of running a job in every region for every hour of the next 48 hours.

## The grid

Each **row** is a region, ordered with the cheapest overall at the top. Each **column** is an hour. The axis shows local time, with the day name at midnight.

The colour of a cell is its cost compared with running now in the comparison region:

- **Blue** is cheaper, and the deeper the blue the bigger the saving.
- **Grey** is about the same.
- **Red** is costlier.

The cell with a ring around it is the **cheapest slot** in the whole window. The summary above the grid names it.

## Choosing an hour

Click any cell, or move the **Hour** slider, to select that hour. The slider is the way to move through hours with the keyboard. The table and the map below then show that hour.

## The table

For the selected hour, each region shows:

| Column | Meaning |
|---|---|
| **Cost** | The index. 1.00 equals running now in the comparison region. |
| **Water L** | Litres for your GPU-hours in that hour. Hover for the low and high range. |
| **CO₂ kg** | Kilograms of CO₂, also with a range on hover. |
| **Wet-bulb °C** | The cooling-relevant temperature. Higher means more cooling water for tower and adiabatic sites. |
| **gCO₂/kWh** | Grid carbon intensity. |

The two last columns are hidden on narrow screens.

## The map

Dots mark the regions, coloured by the same scale. The map is greyscale on purpose, so the only colour you see is cost.

## Things worth noticing

- **A region's cost changes through the day.** Temperature, humidity and the grid mix all move by the hour. Solar lowers carbon in the afternoon, wet-bulb temperature is usually highest then, and carbon often rises at night when solar stops. The grid shows the net effect for each hour.
- **Region often matters more than hour.** Cool, hydro-rich or wind-rich regions can stay cheap around the clock, so for many jobs choosing the place gives most of the saving. See the trace replay on the [Savings](#/docs/guide-savings) page for how much of the saving comes from place and how much from time.
- **Changing GPU-hours changes litres and kilograms, not the colours.** The index is relative, so doubling the job doubles both the chosen slot and the baseline.

## Data labels

A banner appears if any region is using synthetic weather or modelled carbon. A quiet note appears when carbon forecasts hold their last value past their horizon. See [Data and forecasts](#/docs/data-and-forecasts).
