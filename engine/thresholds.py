"""Risk bands per work intensity.

WBGT bands follow the ISO 7243:2017 reference values (Annex A) for
acclimatised workers. Work intensity maps to metabolic rate classes:

=========  ==================  =========================================  =================
Intensity  ISO metabolic class  Typical work                               WBGT limit (°C)
=========  ==================  =========================================  =================
light      1 (~180 W)          vending, driving, sorting, light assembly  30
moderate   2 (~300 W)          street vending on foot, cycling, painting  28
heavy      3 (~415 W)          construction, loading, digging, rickshaw   26
=========  ==================  =========================================  =================

Most outdoor workers in Indian cities are acclimatised by May, so those are
the defaults; ``acclimatised=False`` uses the stricter values (29 / 26 / 23).

Levels:

* ``red``   WBGT >= limit: stop or switch to short work, long rest in shade.
* ``amber`` limit - 2 °C <= WBGT < limit: work with water and regular breaks.
  The 2 °C margin also absorbs the error of estimating WBGT from forecasts.
* ``green`` below that.

When solar radiation is missing we fall back to the heat index, with bands
derived from the NWS categories (caution 27 °C, extreme caution 32 °C,
danger 39 °C, extreme danger 51 °C) shifted one category stricter for heavy
work, since the NWS scale assumes someone resting in shade.
"""

from __future__ import annotations

GREEN, AMBER, RED = "green", "amber", "red"
LEVELS = (GREEN, AMBER, RED)
WORK_INTENSITIES = ("light", "moderate", "heavy")

WBGT_LIMITS_ACCLIMATISED = {"light": 30.0, "moderate": 28.0, "heavy": 26.0}
WBGT_LIMITS_UNACCLIMATISED = {"light": 29.0, "moderate": 26.0, "heavy": 23.0}
WBGT_AMBER_MARGIN = 2.0

# (amber_from, red_from) in °C of heat index
HEAT_INDEX_BANDS = {
    "light": (32.0, 41.0),
    "moderate": (32.0, 39.0),
    "heavy": (27.0, 32.0),
}


def _check_work(work: str) -> None:
    if work not in WORK_INTENSITIES:
        raise ValueError(f"work must be one of {WORK_INTENSITIES}, got {work!r}")


def wbgt_level(wbgt: float, work: str, acclimatised: bool = True) -> str:
    """Map a WBGT value (°C) to green/amber/red for a work intensity."""
    _check_work(work)
    limits = WBGT_LIMITS_ACCLIMATISED if acclimatised else WBGT_LIMITS_UNACCLIMATISED
    limit = limits[work]
    if wbgt >= limit:
        return RED
    if wbgt >= limit - WBGT_AMBER_MARGIN:
        return AMBER
    return GREEN


def heat_index_level(hi: float, work: str) -> str:
    """Map a heat index value (°C) to green/amber/red for a work intensity."""
    _check_work(work)
    amber_from, red_from = HEAT_INDEX_BANDS[work]
    if hi >= red_from:
        return RED
    if hi >= amber_from:
        return AMBER
    return GREEN


def worst(*levels: str) -> str:
    """The most severe of the given levels."""
    return max(levels, key=LEVELS.index)


def step_down(level: str) -> str:
    """One level less severe (red -> amber -> green -> green)."""
    return LEVELS[max(LEVELS.index(level) - 1, 0)]
