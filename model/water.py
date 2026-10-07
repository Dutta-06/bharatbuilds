"""Water per kWh: on-site cooling (WUE_site) and electricity generation (WUE_grid).

On-site, per kWh of IT energy, by cooling design (all numbers in coefficients.yaml):

* ``tower``: chillers plus evaporative cooling towers with a water-side
  economiser. The share of heat leaving by evaporation ramps linearly from 0
  (wet-bulb at or below free_cooling_below_wetbulb_c) to 1 (at or above
  full_evaporative_above_wetbulb_c). Water = share × heat rejected per IT kWh
  × 3.6 / latent heat × C / (C - 1) for C cycles of concentration.
* ``hybrid``: the tower curve shifted warmer (runs dry for longer).
* ``adiabatic``: direct evaporative air cooling. Water is only evaporated when
  outside air is above the supply setpoint: the water needed to cool the
  server airflow (3600 / (cp·ΔT_server) kg of air per kWh) from dry-bulb to
  setpoint, times a bleed factor. It cannot cool below wet-bulb.
* ``air``: zero.

These physics curves give the hour-to-hour *shape*. Each region's *level* is
then calibrated so its annual average matches the operator's disclosed WUE
(``calibration_factor``), because real facilities mix designs and setpoints.

Off-site: litres per kWh of grid electricity is the generation-weighted mean
of per-source consumption factors (Macknick et al. 2012).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from . import coefficients as c

COOLING_TYPES = ("tower", "hybrid", "adiabatic", "air")


def _evaporation_l_per_kwh_heat() -> float:
    return 3.6 / c.value("physics", "latent_heat_vaporisation")  # MJ/kWh ÷ MJ/kg = kg ≈ L


def _tower(t_wb: float, shift: float = 0.0) -> float:
    lo = c.value("site_cooling", "tower", "free_cooling_below_wetbulb_c") + shift
    hi = c.value("site_cooling", "tower", "full_evaporative_above_wetbulb_c") + shift
    share = min(max((t_wb - lo) / (hi - lo), 0.0), 1.0)
    cycles = c.value("site_cooling", "tower", "cycles_of_concentration")
    heat = c.value("site_cooling", "tower", "heat_rejected_per_it_kwh")
    return share * heat * _evaporation_l_per_kwh_heat() * cycles / (cycles - 1)


def _adiabatic(t_db: float, t_wb: float) -> float:
    setpoint = c.value("site_cooling", "adiabatic", "supply_air_setpoint_c")
    if t_db <= setpoint:
        return 0.0
    # Evaporative cooling cannot take air below its wet-bulb.
    delta = t_db - max(setpoint, t_wb)
    if delta <= 0:
        return 0.0
    cp = c.value("physics", "air_specific_heat")  # kJ/(kg·K)
    dt_server = c.value("site_cooling", "adiabatic", "server_air_delta_t_k")
    air_kg_per_kwh = 3600.0 / (cp * dt_server)
    latent_kj_per_kg = c.value("physics", "latent_heat_vaporisation") * 1000.0
    water = air_kg_per_kwh * cp * delta / latent_kj_per_kg
    return water * c.value("site_cooling", "adiabatic", "bleed_factor")


def wue_site_physics(t_wb: float, t_db: float, cooling_type: str) -> float:
    """Uncalibrated on-site water, L per kWh IT, for one hour."""
    if cooling_type == "tower":
        return _tower(t_wb)
    if cooling_type == "hybrid":
        return _tower(t_wb, shift=c.value("site_cooling", "hybrid", "wetbulb_shift_c"))
    if cooling_type == "adiabatic":
        return _adiabatic(t_db, t_wb)
    if cooling_type == "air":
        return 0.0
    raise ValueError(f"cooling_type must be one of {COOLING_TYPES}, got {cooling_type!r}")


def calibration_factor(
    hourly_weather: Iterable[tuple[float, float]],
    cooling_type: str,
    disclosed_annual_wue: float,
) -> float:
    """Scale so the mean of the physics curve over a year of (t_wb, t_db) matches disclosure.

    Returns 1.0 for air cooling or when the curve is zero all year (nothing to scale).
    """
    values = [wue_site_physics(wb, db, cooling_type) for wb, db in hourly_weather]
    if not values:
        raise ValueError("need at least one hour of weather to calibrate")
    mean = sum(values) / len(values)
    return disclosed_annual_wue / mean if mean > 0 else 1.0


def wue_site(t_wb: float, t_db: float, cooling_type: str, scale: float = 1.0) -> float:
    """On-site water, L per kWh IT, for one hour, after regional calibration."""
    return scale * wue_site_physics(t_wb, t_db, cooling_type)


def wue_grid(mix: Mapping[str, float], include_hydro: bool | None = None) -> float:
    """Water consumed per kWh of grid electricity, L/kWh, for a generation mix.

    ``mix`` maps Electricity Maps source names to shares or MW; it is normalised.
    Unknown source names count as ``unknown``.
    """
    factors = c.load()["grid_water_factors"]["values"]
    if include_hydro is None:
        include_hydro = bool(c.value("grid_water_factors", "include_hydro"))
    total = sum(v for v in mix.values() if v and v > 0)
    if total <= 0:
        raise ValueError("generation mix is empty")
    litres = 0.0
    for source, amount in mix.items():
        if not amount or amount <= 0:
            continue
        key = source if source in factors else "unknown"
        if key == "hydro" and not include_hydro:
            continue
        litres += factors[key] * amount / total
    return litres
