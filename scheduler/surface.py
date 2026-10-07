"""The cost surface: per region, per UTC hour, the footprint of one kWh of IT energy.

Footprints are linear in energy, so the surface is computed once per forecast
run with ``it_kwh = 1`` and scaled for each job.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta

from model.cost import Conditions, Footprint, footprint
from model.regions import Region


def hour_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:00")


def parse_key(key: str) -> datetime:
    return datetime.strptime(key[:13], "%Y-%m-%dT%H")


@dataclass(frozen=True)
class Surface:
    """unit[region_id][hour_key] = Footprint for 1 kWh IT."""

    regions: Mapping[str, Region]
    unit: Mapping[str, Mapping[str, Footprint]]
    _prefix: dict = field(default_factory=dict, compare=False, repr=False)

    def hours(self, region_id: str) -> list[str]:
        return sorted(self.unit.get(region_id, {}))

    def covers(self, region_id: str, start: datetime, duration_h: int) -> bool:
        table = self.unit.get(region_id, {})
        return all(hour_key(start + timedelta(hours=i)) in table for i in range(duration_h))

    def window(self, region_id: str, start: datetime, duration_h: int, it_kwh: float) -> Footprint:
        """Footprint of a job using it_kwh spread evenly over duration_h hours from start.

        O(1) via per-region prefix sums when the region's hours are contiguous
        (they always are for forecasts and history); otherwise sums directly.
        """
        table = self.unit[region_id]
        per_hour = it_kwh / duration_h
        pre = self._prefix_for(region_id)
        i = pre["index"].get(hour_key(start)) if pre else None
        if i is not None and i + duration_h <= len(pre["index"]):
            n = duration_h
            sums = {name: (pre[name][i + n] - pre[name][i]) for name in _PREFIXED}
            first = table[hour_key(start)]
            values = {f.name: getattr(first, f.name) for f in fields(Footprint)}
            values.update({name: sums[name] * per_hour for name in _ADDITIVE})
            values.update(hour=hour_key(start), t_wb=sums["t_wb"] / n,
                          wue_site_l_per_kwh=sums["wue_site_l_per_kwh"] / n,
                          wue_grid_l_per_kwh=sums["wue_grid_l_per_kwh"] / n)
            return Footprint(**values)
        hours = [table[hour_key(start + timedelta(hours=i))] for i in range(duration_h)]
        return sum_footprints(hours, per_hour, hour_key(start))

    def _prefix_for(self, region_id: str) -> dict | None:
        if region_id in self._prefix:
            return self._prefix[region_id]
        keys = sorted(self.unit[region_id])
        contiguous = all(parse_key(b) - parse_key(a) == timedelta(hours=1) for a, b in zip(keys, keys[1:]))
        pre = None
        if contiguous and keys:
            pre = {"index": {k: i for i, k in enumerate(keys)}}
            for name in _PREFIXED:
                acc, run = [0.0], 0.0
                for k in keys:
                    run += getattr(self.unit[region_id][k], name)
                    acc.append(run)
                pre[name] = acc
        self._prefix[region_id] = pre
        return pre


def build(regions: Mapping[str, Region], conditions: Mapping[str, Iterable[Conditions]]) -> Surface:
    """Unit footprints for every region-hour that has conditions (hours are UTC keys)."""
    unit: dict[str, dict[str, Footprint]] = {}
    for rid, conds in conditions.items():
        region = regions[rid]
        unit[rid] = {}
        for cond in conds:
            key = hour_key(parse_key(cond.hour))
            unit[rid][key] = footprint(region, Conditions(**{**cond.__dict__, "hour": key}), 1.0)
    return Surface(regions=regions, unit=unit)


_ADDITIVE = ("it_kwh", "facility_kwh", "litres_site", "litres_grid", "litres", "kg_co2",
             "litres_low", "litres_high", "kg_low", "kg_high")
_PREFIXED = _ADDITIVE + ("t_wb", "wue_site_l_per_kwh", "wue_grid_l_per_kwh")


def sum_footprints(units: list[Footprint], kwh_each: float, hour: str) -> Footprint:
    """Sum unit footprints, each scaled to kwh_each. Bands add linearly (errors are
    correlated hour to hour, so this is the conservative choice)."""
    if not units:
        raise ValueError("no hours to sum")
    totals = {name: sum(getattr(u, name) for u in units) * kwh_each for name in _ADDITIVE}
    n = len(units)
    first = units[0]
    values = {f.name: getattr(first, f.name) for f in fields(Footprint)}
    values.update(totals)
    values.update(
        hour=hour,
        t_wb=sum(u.t_wb for u in units) / n,
        wue_site_l_per_kwh=sum(u.wue_site_l_per_kwh for u in units) / n,
        wue_grid_l_per_kwh=sum(u.wue_grid_l_per_kwh for u in units) / n,
    )
    return Footprint(**values)
