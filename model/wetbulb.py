"""Wet-bulb temperature.

``wet_bulb(t, rh, p_hpa)`` solves the psychrometric equation (WMO-No. 8):

    e = e_w(Tw) - A · (1 + 0.000944·Tw) · P · (T - Tw)

for Tw by bisection, where e = RH · e_w(T) and e_w is the Magnus saturation
vapour pressure over water (e_w = 6.112·exp(17.62·T / (243.12 + T)) hPa,
WMO-No. 8). This uses surface pressure, so it is correct at altitude.

``wet_bulb_stull(t, rh)`` is the closed-form Stull (2011) fit. It assumes
sea-level pressure (1013.25 hPa); Stull reports errors between -1 and +0.65 °C
for RH 5-99% and -20-50 °C. It is kept as a cross-check: the two agree near sea level.
"""

from __future__ import annotations

import math

from . import coefficients

SEA_LEVEL_HPA = 1013.25


def saturation_vapour_pressure_hpa(t: float) -> float:
    """Magnus formula over water, hPa (WMO-No. 8)."""
    return 6.112 * math.exp(17.62 * t / (243.12 + t))


def wet_bulb(t: float, rh: float, p_hpa: float = SEA_LEVEL_HPA) -> float:
    """Psychrometric wet-bulb temperature (°C) from air temperature (°C), RH (%) and pressure (hPa)."""
    if not 0 < rh <= 100:
        raise ValueError(f"relative humidity must be in (0, 100], got {rh}")
    a = coefficients.value("physics", "psychrometer_coefficient")
    e = rh / 100.0 * saturation_vapour_pressure_hpa(t)

    def residual(tw: float) -> float:
        return saturation_vapour_pressure_hpa(tw) - a * (1 + 0.000944 * tw) * p_hpa * (t - tw) - e

    lo, hi = t - 60.0, t  # residual(lo) < 0 < residual(hi) for any physical input
    for _ in range(60):
        mid = (lo + hi) / 2
        if residual(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def wet_bulb_stull(t: float, rh: float) -> float:
    """Stull (2011), J. Appl. Meteor. Climatol. 50:2267. Sea-level pressure only."""
    rh = min(max(rh, 5.0), 99.0)
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )
