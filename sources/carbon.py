"""Grid carbon intensity and generation mix per hour.

Two sources share one interface:

* ``ElectricityMaps``: the real thing. Needs ELECTRICITYMAPS_TOKEN. The free tier
  (as far as we know; confirm with your key) gives latest values and the last
  24 h of history for one zone; forecasts and longer ranges may need a paid
  plan. Calls that the key cannot make raise ``CarbonSourceError``.
* ``ModelledProfile``: a fallback so everything runs without a key. It shapes
  the region's typical intensity with a solar dip around local noon, scaled by
  the region's solar share. Every value it returns is marked
  ``source = "modelled"`` and must never be presented as measured.

``for_region`` picks Electricity Maps when a token is set, else the profile.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta

API = "https://api.electricitymap.org/v3"


class CarbonSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GridHour:
    hour: str                  # UTC "YYYY-MM-DDTHH:00"
    ci_g_per_kwh: float
    mix: dict                  # source -> share (sums to ~1) or MW; may be empty
    source: str                # "electricitymaps", "electricitymaps-forecast" or "modelled"


def _hour(text: str) -> str:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%dT%H:00")


class ElectricityMaps:
    name = "electricitymaps"

    def __init__(self, token: str | None = None, timeout: float = 15.0):
        self.token = token or os.environ.get("ELECTRICITYMAPS_TOKEN")
        if not self.token:
            raise CarbonSourceError("ELECTRICITYMAPS_TOKEN is not set")
        self.timeout = timeout

    def _get(self, path: str, **params) -> dict:
        url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"auth-token": self.token, "User-Agent": "pravaah/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            raise CarbonSourceError(f"Electricity Maps {path} for {params.get('zone')}: HTTP {e.code}") from e

    @staticmethod
    def _mix(breakdown: dict | None) -> dict:
        if not breakdown:
            return {}
        cons = breakdown.get("powerConsumptionBreakdown") or breakdown.get("powerProductionBreakdown") or {}
        mix = {k.replace(" ", "_"): v for k, v in cons.items() if v and v > 0}
        mix.pop("battery_discharge", None)
        if "hydro_discharge" in mix:
            mix["hydro"] = mix.get("hydro", 0) + mix.pop("hydro_discharge")
        return mix

    def history(self, zone: str) -> list[GridHour]:
        """Last 24 hours (free tier)."""
        ci = self._get("carbon-intensity/history", zone=zone)["history"]
        try:
            pb = {_hour(x["datetime"]): x for x in self._get("power-breakdown/history", zone=zone)["history"]}
        except CarbonSourceError:
            pb = {}
        return [GridHour(_hour(x["datetime"]), float(x["carbonIntensity"]),
                         self._mix(pb.get(_hour(x["datetime"]))), self.name)
                for x in ci if x.get("carbonIntensity") is not None]

    def forecast(self, zone: str) -> list[GridHour]:
        """Up to 72 h ahead, if the key allows. Mix is not forecast; callers reuse the latest."""
        data = self._get("carbon-intensity/forecast", zone=zone)["forecast"]
        return [GridHour(_hour(x["datetime"]), float(x["carbonIntensity"]), {}, "electricitymaps-forecast")
                for x in data if x.get("carbonIntensity") is not None]

    def latest(self, zone: str) -> GridHour:
        x = self._get("carbon-intensity/latest", zone=zone)
        try:
            mix = self._mix(self._get("power-breakdown/latest", zone=zone))
        except CarbonSourceError:
            mix = {}
        return GridHour(_hour(x["datetime"]), float(x["carbonIntensity"]), mix, self.name)


class ModelledProfile:
    """Typical intensity with a midday solar dip. Clearly labelled; not data."""

    name = "modelled"

    def __init__(self, typical_ci: float, mix: dict, lon: float):
        self.typical_ci = typical_ci
        self.mix = dict(mix)
        self.lon = lon
        total = sum(mix.values()) or 1.0
        self.solar_share = mix.get("solar", 0.0) / total

    def at(self, hour_utc: datetime) -> GridHour:
        local_solar_hour = (hour_utc.hour + self.lon / 15.0) % 24
        sun = max(0.0, math.cos((local_solar_hour - 12.0) / 12.0 * math.pi))  # 1 at noon, 0 at night
        # Solar output peaks ~3× its daily-average share at noon; it displaces the
        # marginal (fossil) mix, so intensity drops proportionally.
        dip = min(0.9, 3.0 * self.solar_share * sun)
        mean_dip = 3.0 * self.solar_share / math.pi  # average of the dip over a day
        ci = self.typical_ci * (1 - dip) / max(0.1, 1 - mean_dip)
        return GridHour(hour_utc.strftime("%Y-%m-%dT%H:00"), round(ci, 1), self.mix, self.name)

    def hours(self, start_utc: datetime, n: int) -> list[GridHour]:
        return [self.at(start_utc + timedelta(hours=i)) for i in range(n)]


def for_region(region) -> ElectricityMaps | ModelledProfile:
    """Electricity Maps when a token is set and the region has a zone; else the profile."""
    if os.environ.get("ELECTRICITYMAPS_TOKEN") and region.electricity_maps_zone:
        return ElectricityMaps()
    if region.typical_ci_g_per_kwh is None:
        raise CarbonSourceError(f"{region.id}: no Electricity Maps token and no typical_ci_g_per_kwh")
    return ModelledProfile(region.typical_ci_g_per_kwh, region.grid_mix, region.lon)
