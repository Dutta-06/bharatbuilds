"""Waterlogging risk from forecast rainfall, hotspot membership and elevation.

The trigger is rainfall *intensity*: the total over the trailing 3 hours
(this hour and the two before it). Delhi's storm drains were designed for
roughly 50 mm/day; in practice known hotspots (underpasses, low-lying
crossings) flood after 15-20 mm in a short burst, and the wider city after
~40 mm in 3 h, which the IMD would class as heavy rain over 24 h already.

Base thresholds (mm per 3 h):

=================  ===========  =========
Cell               amber from   red from
=================  ===========  =========
no hotspot         15           40
has a hotspot      7.5          20
=================  ===========  =========

Elevation: a cell more than ``LOW_LYING_M`` below the city reference
elevation collects runoff from its neighbours, so its thresholds are
multiplied by ``LOW_LYING_FACTOR`` (0.75).

Drainage lag: water does not leave when the rain stops. For two hours after
a red hour the level stays at least amber.

These thresholds are a starting point to be checked against reported
flooding (Step 8 reports feed back into this).
"""

from __future__ import annotations

from collections.abc import Sequence

from .thresholds import AMBER, GREEN, RED, step_down, worst

WINDOW_HOURS = 3
BASE_THRESHOLDS_MM = (15.0, 40.0)
HOTSPOT_THRESHOLDS_MM = (7.5, 20.0)
LOW_LYING_M = 5.0
LOW_LYING_FACTOR = 0.75
DRAINAGE_LAG_HOURS = 2


def thresholds_mm(
    has_hotspot: bool,
    elevation_m: float | None = None,
    city_ref_elevation_m: float | None = None,
) -> tuple[float, float]:
    """(amber_from, red_from) in mm per 3 h for a cell."""
    amber, red = HOTSPOT_THRESHOLDS_MM if has_hotspot else BASE_THRESHOLDS_MM
    if (
        elevation_m is not None
        and city_ref_elevation_m is not None
        and city_ref_elevation_m - elevation_m > LOW_LYING_M
    ):
        amber, red = amber * LOW_LYING_FACTOR, red * LOW_LYING_FACTOR
    return amber, red


def rolling_sums(precip_mm: Sequence[float], window: int = WINDOW_HOURS) -> list[float]:
    """Trailing sums: element i is the total of hours i-window+1 .. i."""
    out = []
    for i in range(len(precip_mm)):
        out.append(sum(max(p or 0.0, 0.0) for p in precip_mm[max(0, i - window + 1) : i + 1]))
    return out


def level_for(total_mm: float, amber_from: float, red_from: float) -> str:
    if total_mm >= red_from:
        return RED
    if total_mm >= amber_from:
        return AMBER
    return GREEN


def waterlogging_levels(
    precip_mm: Sequence[float],
    has_hotspot: bool = False,
    elevation_m: float | None = None,
    city_ref_elevation_m: float | None = None,
    lead_in: Sequence[float] = (),
) -> list[str]:
    """One level per hour of ``precip_mm``.

    ``lead_in`` is rainfall for the hours just before the strip starts, so the
    first hours' 3 h totals and drainage lag are not cut short.
    """
    amber_from, red_from = thresholds_mm(has_hotspot, elevation_m, city_ref_elevation_m)
    series = list(lead_in) + list(precip_mm)
    raw = [level_for(s, amber_from, red_from) for s in rolling_sums(series)]

    lagged = []
    for i, level in enumerate(raw):
        for back in range(1, DRAINAGE_LAG_HOURS + 1):
            if i - back >= 0 and raw[i - back] == RED:
                level = worst(level, step_down(RED))
        lagged.append(level)
    return lagged[len(lead_in) :]
