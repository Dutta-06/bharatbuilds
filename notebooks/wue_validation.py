# %% [markdown]
# # Validating the site-WUE curves against published figures
#
# Plan Step 1 asks us to reproduce at least two published WUE figures within a
# stated tolerance. Calibration (scripts/calibrate_wue.py) forces the annual
# mean to match disclosure, so validating *after* calibration proves nothing.
# Here we use the **uncalibrated physics curves** and a real year of weather,
# and compare the annual mean with what AWS discloses.
#
# **Tolerance:** within ±40% for cooling-tower regions (cycles of concentration
# alone spans 3-10), and the same order of magnitude (within 3×) for adiabatic
# regions, whose disclosed WUE is near zero.
#
# Open this in Jupyter or VS Code (it is a "percent" script: each `# %%` is a
# cell), or run it with `python notebooks/wue_validation.py`. Needs internet
# access to archive-api.open-meteo.com.

# %%
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() if (Path.cwd() / "model").exists() else Path(__file__).resolve().parent.parent))

from model import regions
from sources import openmeteo
from model.water import wue_site_physics
from model.wetbulb import wet_bulb

TOLERANCE = {"tower": (0.6, 1.4), "hybrid": (0.6, 1.4), "adiabatic": (1 / 3, 3.0)}
CASES = ["ap-southeast-1", "eu-west-1", "us-east-1", "eu-central-1"]

# %%
start, end = openmeteo.last_full_year()
rows = []
for rid in CASES:
    r = regions.get(rid)
    hours = openmeteo.history(r.lat, r.lon, start, end)
    values = [wue_site_physics(wet_bulb(t, rh, p), t, r.cooling_type) for _, t, rh, p in hours]
    modelled = sum(values) / len(values)
    lo, hi = TOLERANCE[r.cooling_type]
    ratio = modelled / r.disclosed_wue
    rows.append((rid, r.cooling_type, modelled, r.disclosed_wue, ratio, lo <= ratio <= hi))

# %%
print(f"weather {start:%Y-%m-%d} to {end:%Y-%m-%d}\n")
print(f"{'region':16} {'cooling':10} {'modelled':>9} {'disclosed':>9} {'ratio':>6}  pass")
for rid, ct, m, d, ratio, ok in rows:
    print(f"{rid:16} {ct:10} {m:9.3f} {d:9.3f} {ratio:6.2f}  {'yes' if ok else 'NO'}")
passed = sum(ok for *_, ok in rows)
print(f"\n{passed} of {len(rows)} within tolerance (plan requires at least 2)")

# %% [markdown]
# Record the output here when you run it, with the date, so the blog can cite it.
