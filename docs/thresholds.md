# How Chhaanv decides green, amber, red

One page, for anyone on the team who has to explain this to a judge.

## Heat

**Why WBGT and not temperature.** 40 °C in dry air and 34 °C in humid air can be
equally dangerous, because sweat stops cooling you when the air is wet. Sun on
your body adds heat too, and wind takes it away. Wet Bulb Globe Temperature (WBGT)
combines all four. It is the index the international standard for heat stress at
work (ISO 7243) is built on.

**How we estimate it** (`engine/wbgt.py`). A forecast gives temperature, humidity,
sunshine and wind, but not WBGT itself, so we calculate it:

1. Wet-bulb temperature from temperature and humidity (Stull 2011 formula).
2. Black-globe temperature: how hot a black ball in the sun gets, from a heat
   balance (sun in, wind and radiation out).
3. WBGT = 0.7 × natural wet bulb + 0.2 × globe + 0.1 × air temperature.

When the forecast has no sunshine data, we fall back to the NOAA heat index
(`engine/heat_index.py`). The Australian BoM shortcut formula is in the code as a
cross-check. We don't use it on its own because it overshoots badly in humid heat.

**Bands** (`engine/thresholds.py`): ISO 7243 limits for acclimatised workers.

| Work | Examples | Amber from | Red from |
|---|---|---|---|
| light | driving, vending, sorting | 28 °C WBGT | 30 °C |
| moderate | walking vendors, cycling, painting | 26 °C | 28 °C |
| heavy | construction, loading, rickshaw | 24 °C | 26 °C |

* **Red:** above the ISO limit. Stop, or work in short bursts with long rests in shade.
* **Amber:** within 2 °C of the limit. Work with water and a break every hour. The
  2 °C margin also covers the error of estimating WBGT from a forecast (±2 °C).
* **Green:** below that.

Sanity checks covered by tests: a 44 °C, 60 % humidity afternoon is red for heavy
work, and a 28 °C morning is green.

## Waterlogging

`engine/waterlogging.py` adds up the last 3 hours of rain.

| Cell | Amber from | Red from |
|---|---|---|
| normal | 15 mm / 3 h | 40 mm / 3 h |
| has a known hotspot (underpass, low crossing) | 7.5 mm | 20 mm |

A cell more than 5 m lower than the city's reference elevation has its thresholds
multiplied by 0.75, because water runs into it from its neighbours. Water also
doesn't drain the moment the rain stops, so the level stays at least amber for
two hours after a red hour.

These numbers are a starting point. Community reports (Step 8) are how we check
and tune them.

## Safe windows

`engine/windows.py` groups the 48 hours into runs of the same colour and writes
two or three sentences: what to do now, the next danger period, and the next safe
period. All the words are in `engine/strings/windows.json` (English and Hindi),
so a translator can change the wording without touching code.
