"""NOAA / US National Weather Service heat index.

Used as the fallback heat metric when solar radiation is missing from the
forecast, because without it we cannot estimate the globe temperature.

Algorithm (https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml):

1. Compute the simple Steadman form
   ``HI = 0.5 * (T + 61 + (T - 68) * 1.2 + RH * 0.094)`` (°F).
2. If the average of that and T is 80 °F or more, use the Rothfusz
   regression instead, with the NWS low-humidity and high-humidity
   adjustments.

Limits: heat index is a shade, light-wind measure of how hot it *feels*; it
ignores sun and wind and was not designed for working people. Its bands in
``thresholds.py`` are therefore set more cautiously than the NWS ones.
"""

from __future__ import annotations

import math


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def heat_index_f(t_f: float, rh: float) -> float:
    """Heat index in °F from air temperature (°F) and relative humidity (%)."""
    simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    if (simple + t_f) / 2.0 < 80.0:
        return simple

    hi = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 0.00683783 * t_f * t_f
        - 0.05481717 * rh * rh
        + 0.00122874 * t_f * t_f * rh
        + 0.00085282 * t_f * rh * rh
        - 0.00000199 * t_f * t_f * rh * rh
    )
    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        hi -= ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        hi += ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
    return hi


def heat_index(t: float, rh: float) -> float:
    """Heat index in °C from air temperature (°C) and relative humidity (%)."""
    return f_to_c(heat_index_f(c_to_f(t), rh))
