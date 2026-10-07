"""Footprint, cost and receipt for running a job in one (region, hour) slot.

Per region r and hour h, for a job with IT energy E_it (kWh):

    E_facility   = E_it × PUE(r)
    litres(r,h)  = E_it × WUE_site(r,h) + E_facility × WUE_grid(r,h)
    kg(r,h)      = E_facility × CI(r,h) / 1000
    cost(r,h)    = w_water × litres × S(r) + w_carbon × kg

This differs from the plan's one-line formula in one deliberate way: WUE_site
is defined per kWh of IT energy, while grid water and carbon apply to all the
electricity the facility draws, including cooling overhead (PUE).

With ``baseline`` given, cost is normalised so each term is relative to
running now, here: cost = w_water × (litres·S)/(litres_b·S_b) + w_carbon × kg/kg_b.
That makes weights unitless (0.5/0.5 means "care equally").
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from . import coefficients as c
from .regions import Region
from .water import wue_grid, wue_site
from .wetbulb import SEA_LEVEL_HPA, wet_bulb


@dataclass(frozen=True)
class Conditions:
    """Weather and grid for one region-hour."""

    hour: str                       # ISO local or UTC; carried through to the receipt
    t_db: float                     # °C
    rh: float                       # %
    ci_g_per_kwh: float             # carbon intensity of consumed electricity
    p_hpa: float = SEA_LEVEL_HPA    # surface pressure
    grid_mix: dict | None = None    # power breakdown for this hour; falls back to region's
    t_wb: float | None = None       # model-corrected wet-bulb (Step 4); computed from t_db/rh/p if None


@dataclass(frozen=True)
class Footprint:
    region: str
    hour: str
    it_kwh: float
    facility_kwh: float
    t_wb: float
    wue_site_l_per_kwh: float
    wue_grid_l_per_kwh: float
    litres_site: float
    litres_grid: float
    litres: float
    kg_co2: float
    litres_low: float
    litres_high: float
    kg_low: float
    kg_high: float
    energy_basis: str               # "estimated" or "measured"

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _rel(*parts: float) -> float:
    return math.sqrt(sum(p * p for p in parts))


def energy_uncertainty(measured: bool) -> float:
    if measured:
        return c.value("measured_energy", "uncertainty")
    return _rel(
        c.uncertainty("job_energy", "gpu_utilisation"),
        c.uncertainty("job_energy", "server_overhead"),
        float(c.load()["gpus"]["uncertainty"]),
    )


def footprint(region: Region, cond: Conditions, it_kwh: float, measured: bool = False) -> Footprint:
    """Litres and kg CO2 for a job of ``it_kwh`` in ``region`` under ``cond``."""
    if it_kwh <= 0:
        raise ValueError("it_kwh must be positive")
    mix = cond.grid_mix or region.grid_mix
    if not mix:
        raise ValueError(f"no grid mix for {region.id}; pass Conditions.grid_mix")

    t_wb = cond.t_wb if cond.t_wb is not None else wet_bulb(cond.t_db, cond.rh, cond.p_hpa)
    site = wue_site(t_wb, cond.t_db, region.cooling_type, region.wue_scale)
    grid = wue_grid(mix)
    facility_kwh = it_kwh * region.pue

    litres_site = it_kwh * site
    litres_grid = facility_kwh * grid
    kg = facility_kwh * cond.ci_g_per_kwh / 1000.0

    e = energy_uncertainty(measured)
    site_u = c.load()["regional_wue"]["uncertainty"] if region.calibrated else 0.5
    grid_u = c.load()["grid_water_factors"]["uncertainty"]
    ci_u = c.value("carbon_intensity", "uncertainty")
    pue_u = c.uncertainty("pue", "default")
    band_site = litres_site * _rel(e, site_u)
    band_grid = litres_grid * _rel(e, grid_u, pue_u)
    band_kg = kg * _rel(e, ci_u, pue_u)
    band_l = math.hypot(band_site, band_grid)

    return Footprint(
        region=region.id, hour=cond.hour, it_kwh=it_kwh, facility_kwh=facility_kwh, t_wb=t_wb,
        wue_site_l_per_kwh=site, wue_grid_l_per_kwh=grid,
        litres_site=litres_site, litres_grid=litres_grid, litres=litres_site + litres_grid,
        kg_co2=kg,
        litres_low=max(0.0, litres_site + litres_grid - band_l),
        litres_high=litres_site + litres_grid + band_l,
        kg_low=max(0.0, kg - band_kg), kg_high=kg + band_kg,
        energy_basis="measured" if measured else "estimated",
    )


@dataclass(frozen=True)
class Weights:
    water: float = 0.5
    carbon: float = 0.5

    def __post_init__(self):
        if self.water < 0 or self.carbon < 0 or self.water + self.carbon == 0:
            raise ValueError("weights must be non-negative and not both zero")


def cost(fp: Footprint, region: Region, weights: Weights = Weights(),
         baseline: tuple[Footprint, Region] | None = None) -> float:
    """Scalar cost of a slot; lower is better. See module docstring."""
    water = fp.litres * region.stress_multiplier
    if baseline is None:
        return weights.water * water + weights.carbon * fp.kg_co2
    b_fp, b_region = baseline
    b_water = b_fp.litres * b_region.stress_multiplier
    water_term = water / b_water if b_water > 0 else (0.0 if water == 0 else 1.0)
    carbon_term = fp.kg_co2 / b_fp.kg_co2 if b_fp.kg_co2 > 0 else (0.0 if fp.kg_co2 == 0 else 1.0)
    return weights.water * water_term + weights.carbon * carbon_term


def rescale(fp: Footprint, measured_it_kwh: float) -> Footprint:
    """The same slot with measured energy in place of the estimate (everything scales with E)."""
    k = measured_it_kwh / fp.it_kwh
    e_est, e_meas = energy_uncertainty(False), energy_uncertainty(True)

    def band(value: float, low: float, high: float) -> tuple[float, float]:
        # Replace the energy part of the band: shrink proportionally, conservatively.
        half = (high - low) / 2 * k * (e_meas / e_est if e_est else 1.0)
        return max(0.0, value * k - half), value * k + half

    l_lo, l_hi = band(fp.litres, fp.litres_low, fp.litres_high)
    k_lo, k_hi = band(fp.kg_co2, fp.kg_low, fp.kg_high)
    return Footprint(
        **{**asdict(fp),
           "it_kwh": measured_it_kwh, "facility_kwh": fp.facility_kwh * k,
           "litres_site": fp.litres_site * k, "litres_grid": fp.litres_grid * k,
           "litres": fp.litres * k, "kg_co2": fp.kg_co2 * k,
           "litres_low": l_lo, "litres_high": l_hi, "kg_low": k_lo, "kg_high": k_hi,
           "energy_basis": "measured"}
    )


def receipt(chosen: Footprint, baseline: Footprint, measured_it_kwh: float | None = None) -> dict:
    """What running in the chosen slot saved versus running now, here.

    With ``measured_it_kwh`` both slots are rescaled to the measured energy, so the
    comparison is like for like.
    """
    if measured_it_kwh is not None:
        chosen, baseline = rescale(chosen, measured_it_kwh), rescale(baseline, measured_it_kwh)
    saved_l = baseline.litres - chosen.litres
    saved_kg = baseline.kg_co2 - chosen.kg_co2

    def pct(saved: float, base: float) -> float | None:
        return round(100.0 * saved / base, 1) if base > 0 else None

    return {
        "chosen": chosen.as_dict(),
        "baseline": baseline.as_dict(),
        "energy_basis": chosen.energy_basis,
        "saved": {
            "litres": round(saved_l, 3),
            "litres_pct": pct(saved_l, baseline.litres),
            "kg_co2": round(saved_kg, 4),
            "kg_co2_pct": pct(saved_kg, baseline.kg_co2),
        },
        "note": (
            "Water is modelled from published cooling curves calibrated to disclosed regional WUE, "
            "and grid-average water factors; absolute litres are uncertain (see low/high), "
            "the ranking between slots is more robust."
        ),
    }
