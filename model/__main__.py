"""CLI: litres of water and kg CO2 for a job in one region and hour.

    python -m model --region ap-south-1 --hour 2026-10-10T15:00 --gpu-hours 4
    python -m model --region ap-south-1 --hour 2026-10-10T15:00 --gpu-hours 4 --compare
    python -m model --region eu-north-1 --hour 2026-10-10T03:00 --gpu-hours 4 \\
                    --temp 8 --rh 85 --pressure 1012 --ci 30      # offline

Hours are UTC. Weather comes from Open-Meteo unless --temp/--rh are given.
Carbon intensity comes from --ci, else the region's placeholder typical value.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import energy, openmeteo, regions
from .cost import Conditions, Weights, cost, footprint


def conditions_for(region, hour_text, args) -> tuple[Conditions, list[str]]:
    notes = []
    if args.temp is not None and args.rh is not None:
        t, rh, p = args.temp, args.rh, args.pressure
    else:
        t, rh, p = openmeteo.hour_weather(region.lat, region.lon, openmeteo.parse_hour(hour_text))
    ci = args.ci if args.ci is not None else region.typical_ci_g_per_kwh
    if args.ci is None:
        notes.append(f"{region.id}: carbon intensity is the placeholder typical value, not live")
    if not region.calibrated:
        notes.append(f"{region.id}: site WUE not yet calibrated to disclosed WUE (run scripts/calibrate_wue.py)")
    return Conditions(hour=hour_text, t_db=t, rh=rh, p_hpa=p, ci_g_per_kwh=ci), notes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m model", description=__doc__.split("\n")[0])
    p.add_argument("--region", required=True, choices=sorted(regions.load()))
    p.add_argument("--hour", required=True, help="UTC hour, e.g. 2026-10-10T15:00")
    p.add_argument("--gpu-hours", type=float, required=True)
    p.add_argument("--gpu", default="a100")
    p.add_argument("--temp", type=float, help="air temperature °C (skips Open-Meteo)")
    p.add_argument("--rh", type=float, help="relative humidity %%")
    p.add_argument("--pressure", type=float, default=1013.25, help="surface pressure hPa")
    p.add_argument("--ci", type=float, help="carbon intensity gCO2/kWh")
    p.add_argument("--compare", action="store_true", help="also show every other region at that hour")
    p.add_argument("--w-water", type=float, default=0.5)
    p.add_argument("--w-carbon", type=float, default=0.5)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.compare and args.temp is not None:
        p.error("--compare fetches weather per region; drop --temp/--rh")
    it_kwh = energy.job_it_kwh(args.gpu_hours, args.gpu)
    weights = Weights(args.w_water, args.w_carbon)
    targets = [regions.get(args.region)]
    if args.compare:
        targets += [r for rid, r in regions.load().items() if rid != args.region]

    rows, notes = [], []
    try:
        base_region = targets[0]
        base_cond, n = conditions_for(base_region, args.hour, args)
        notes += n
        base_fp = footprint(base_region, base_cond, it_kwh)
        for region in targets:
            if region is base_region:
                fp = base_fp
            else:
                cond, n = conditions_for(region, args.hour, args)
                notes += n
                fp = footprint(region, cond, it_kwh)
            rows.append((region, fp, cost(fp, region, weights, baseline=(base_fp, base_region))))
    except OSError as e:
        print(f"Could not reach Open-Meteo ({e}). Pass --temp and --rh to run offline.", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"it_kwh": it_kwh, "gpu": args.gpu, "gpu_hours": args.gpu_hours,
                          "rows": [{**fp.as_dict(), "cost": round(c, 4)} for _, fp, c in rows],
                          "notes": notes}, ensure_ascii=False, indent=2))
        return 0

    print(f"{args.gpu_hours} GPU-hours on {args.gpu.upper()} ≈ {it_kwh:.2f} kWh IT, hour {args.hour} UTC\n")
    print(f"{'region':16} {'T_wb':>5} {'site L':>7} {'grid L':>7} {'litres (low-high)':>22} "
          f"{'kg CO2 (low-high)':>22} {'cost':>6}")
    for region, fp, c in sorted(rows, key=lambda r: r[2]):
        print(f"{region.id:16} {fp.t_wb:5.1f} {fp.litres_site:7.2f} {fp.litres_grid:7.2f} "
              f"{fp.litres:7.2f} ({fp.litres_low:5.2f}-{fp.litres_high:5.2f})  "
              f"{fp.kg_co2:7.3f} ({fp.kg_low:5.3f}-{fp.kg_high:5.3f})  {c:6.3f}")
    print("\ncost: 1.000 = running in", args.region, f"(weights water {weights.water}, carbon {weights.carbon})")
    for note in dict.fromkeys(notes):
        print("note:", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
