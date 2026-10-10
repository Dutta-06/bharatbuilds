"""Conditional manufacturer-curve interpolation. No emissions factors assumed."""
import math


def fuel_rate(curve, demand_kw, capacity_kw):
    if not curve or not curve.get("source"):
        return {"status": "UNAVAILABLE", "reason": "No sourced manufacturer fuel curve configured."}
    points = curve.get("points", [])
    if capacity_kw <= 0 or len(points) < 2:
        return {"status": "UNAVAILABLE", "reason": "Capacity and at least two documented operating points required."}
    loads = [p.get("load_fraction") for p in points]
    rates = [p.get("litres_per_hour") for p in points]
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in loads + rates) or any(a >= b for a, b in zip(loads, loads[1:])) or loads[-1] > 1:
        return {"status": "UNAVAILABLE", "reason": "Invalid or unordered manufacturer operating points."}
    fraction = demand_kw / capacity_kw
    if fraction < loads[0] or fraction > loads[-1]:
        return {"status": "UNAVAILABLE", "reason": "Demand outside documented load range; extrapolation rejected."}
    for left, right in zip(points, points[1:]):
        if left["load_fraction"] <= fraction <= right["load_fraction"]:
            weight = (fraction - left["load_fraction"]) / (right["load_fraction"] - left["load_fraction"])
            rate = left["litres_per_hour"] + weight * (right["litres_per_hour"] - left["litres_per_hour"])
            return {"status": "MODELED", "litres_per_hour": round(rate, 6), "source": curve["source"],
                    "load_fraction": fraction, "assumption": "Conditional interpolation; manufacturer conditions and all facility loads must apply."}
