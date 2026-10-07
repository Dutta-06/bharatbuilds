"""Wet Bulb Globe Temperature (WBGT) estimation from standard forecast variables.

WBGT is the heat-stress index ISO 7243 is built on. Measuring it needs three
instruments (a natural wet-bulb thermometer, a 150 mm black globe and a dry
bulb); weather forecasts give us none of them directly, so we estimate.

Two estimators live here:

``wbgt_bom(t, rh)``
    The Australian Bureau of Meteorology approximation::

        e    = (rh / 100) * 6.105 * exp(17.27 * t / (237.7 + t))   # vapour pressure, hPa
        WBGT = 0.567 * t + 0.393 * e + 3.94

    It uses only air temperature and humidity and assumes "moderately high
    radiation levels in light wind". Limits: it cannot see clouds, night or
    wind, and it overestimates badly at high temperature *and* high humidity
    (44 °C / 60 % RH gives ~50 °C, which is not physical). We keep it as a
    reference and a cross-check, not as the primary estimate.

``wbgt_outdoor(t, rh, solar, wind)``
    The primary estimate, using the ISO 7243 outdoor weighting::

        WBGT = 0.7 * Tnw + 0.2 * Tg + 0.1 * Ta

    * ``Tw`` (psychrometric wet bulb) from Stull (2011), "Wet-bulb temperature
      from relative humidity and air temperature", J. Appl. Meteor. Climatol.
      Valid for RH 5-99 % and -20 to 50 °C; error under ~1 °C.
    * ``Tg`` (black globe temperature) from a steady-state heat balance of a
      0.15 m globe: absorbed shortwave = convective loss + net longwave loss.
      Convection coefficient for a sphere in forced flow (ISO 7726):
      ``h = 6.3 * v**0.6 / D**0.4``. The mean shortwave flux on a sphere is
      taken as 0.4 x global horizontal radiation (direct/4 + diffuse/2 +
      ground-reflected/2 at a high sun). Sky and ground longwave are assumed
      to balance at air temperature.
    * ``Tnw`` (natural wet bulb) = Tw + 0.0015 * solar. The natural wet bulb
      sits above the psychrometric one in sunshine because the wick absorbs
      radiation and is not forcibly ventilated; an order-of-magnitude wick
      heat balance gives roughly 0.5-1.5 °C at 300-900 W/m2. This is an
      allowance, not a fitted coefficient.

    Inputs: air temperature (°C, 2 m), relative humidity (%), global
    horizontal shortwave radiation (W/m2), wind speed at 10 m (m/s; converted
    to 2 m with a power-law profile). Wind is floored at 0.5 m/s because
    still air is never truly still around a person.

    Limits: no cloud-type, surface (asphalt vs grass) or urban-canyon
    effects; globe estimate is less reliable at very low sun angles. Expect
    errors of about ±2 °C WBGT, which is why thresholds use a 2 °C amber band.
"""

from __future__ import annotations

import math

STEFAN_BOLTZMANN = 5.670374419e-8  # W m-2 K-4
GLOBE_DIAMETER_M = 0.15
GLOBE_EMISSIVITY = 0.95
GLOBE_ABSORPTIVITY = 0.95
SPHERE_SHORTWAVE_FRACTION = 0.4
NATURAL_WET_BULB_SOLAR_ALLOWANCE = 0.0015  # °C per W/m2
MIN_WIND_MS = 0.5
WIND_10M_TO_2M = (2.0 / 10.0) ** 0.2  # ~0.72, open-terrain power law


def vapour_pressure_hpa(t: float, rh: float) -> float:
    """Actual vapour pressure (hPa) from air temperature (°C) and RH (%)."""
    return (rh / 100.0) * 6.105 * math.exp(17.27 * t / (237.7 + t))


def wbgt_bom(t: float, rh: float) -> float:
    """Australian BoM WBGT approximation (°C). See module docstring for limits."""
    return 0.567 * t + 0.393 * vapour_pressure_hpa(t, rh) + 3.94


def wet_bulb_stull(t: float, rh: float) -> float:
    """Psychrometric wet-bulb temperature (°C), Stull (2011)."""
    rh = min(max(rh, 5.0), 99.0)
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


def globe_temperature(t: float, solar: float, wind_10m: float) -> float:
    """Black globe temperature (°C) from a steady-state heat balance.

    Solves  absorbed = h * (Tg - Ta) + eps * sigma * (Tg^4 - Ta^4)  by bisection.
    """
    solar = max(solar, 0.0)
    if solar == 0.0:
        return t
    v = max(wind_10m * WIND_10M_TO_2M, MIN_WIND_MS)
    h = 6.3 * v**0.6 / GLOBE_DIAMETER_M**0.4
    absorbed = GLOBE_ABSORPTIVITY * SPHERE_SHORTWAVE_FRACTION * solar
    ta_k = t + 273.15

    def imbalance(tg_k: float) -> float:
        return (
            h * (tg_k - ta_k)
            + GLOBE_EMISSIVITY * STEFAN_BOLTZMANN * (tg_k**4 - ta_k**4)
            - absorbed
        )

    lo, hi = ta_k, ta_k + 60.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if imbalance(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0 - 273.15


def natural_wet_bulb(t: float, rh: float, solar: float) -> float:
    """Natural wet-bulb temperature (°C): Stull wet bulb plus a solar allowance."""
    return wet_bulb_stull(t, rh) + NATURAL_WET_BULB_SOLAR_ALLOWANCE * max(solar, 0.0)


def wbgt_outdoor(t: float, rh: float, solar: float, wind_10m: float) -> float:
    """Outdoor WBGT (°C) using the ISO 7243 weighting. See module docstring."""
    tnw = natural_wet_bulb(t, rh, solar)
    tg = globe_temperature(t, solar, wind_10m)
    return 0.7 * tnw + 0.2 * tg + 0.1 * t
