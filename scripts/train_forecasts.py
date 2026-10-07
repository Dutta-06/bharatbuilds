"""Step 4: train and judge the wet-bulb and carbon models per region.

    pip install -r requirements-dev.txt     # includes scikit-learn
    python scripts/train_forecasts.py --days 60

Wet-bulb: Open-Meteo's Historical Forecast API (what the forecast said) against the
archive (what happened), last N days; persistence = observed wet-bulb 24 h earlier.
The archived forecast is stitched from short leads, so this learns the provider's
systematic bias by hour and season rather than its error growth with lead time.

Carbon: real (non-modelled) rows in data/history/<region>.csv. The free Electricity
Maps tier gives 24 h, so carbon models need history accumulated by the deployed
pipeline first; regions without enough are skipped and say so.

Each model is kept only if its held-out MAE (last 7 days) beats persistence and the
provider. Writes forecasting/models/<region>-<target>.json (with the verdict) and
forecasting/models/metrics.json. The predict Lambda loads only use_model=true files.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forecasting.evaluate import fit_and_judge  # noqa: E402
from forecasting.features import CARBON_FEATURES, WETBULB_FEATURES, carbon_row, wetbulb_row  # noqa: E402
from model import regions as region_config  # noqa: E402
from model.wetbulb import wet_bulb  # noqa: E402
from sources import openmeteo  # noqa: E402

OUT = ROOT / "forecasting" / "models"
HIST_FC = "https://historical-forecast-api.open-meteo.com/v1/forecast"
TEST_DAYS = 7


def series(url, region, start, end) -> dict:
    raw = openmeteo._get(url, {"latitude": region.lat, "longitude": region.lon, "hourly": ",".join(openmeteo.VARS),
                               "timezone": "UTC", "start_date": f"{start:%Y-%m-%d}", "end_date": f"{end:%Y-%m-%d}"},
                         timeout=60.0)
    h = raw["hourly"]
    return {t: (T, RH, P) for t, T, RH, P in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"],
                                                   h["surface_pressure"]) if None not in (T, RH, P)}


def wetbulb_dataset(region, days: int):
    end = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=6)
    start = end - timedelta(days=days)
    fc = series(HIST_FC, region, start, end)
    obs = series(openmeteo.ARCHIVE_URL, region, start, end)
    hours = sorted(set(fc) & set(obs))
    obs_wb = {t: wet_bulb(T, max(RH, 1), P) for t, (T, RH, P) in obs.items()}
    fc_wb = {t: wet_bulb(T, max(RH, 1), P) for t, (T, RH, P) in fc.items()}
    rows, y, pers, prov, test = [], [], [], [], []
    cutoff = hours[-1][:10] if hours else ""
    test_from = (datetime.strptime(cutoff, "%Y-%m-%d") - timedelta(days=TEST_DAYS - 1)).strftime("%Y-%m-%d") if hours else ""
    for t in hours:
        prev = (datetime.strptime(t, "%Y-%m-%dT%H:%M") - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
        if prev not in obs_wb:
            continue
        T, RH, _ = fc[t]
        p_wb = fc_wb[t]
        residual = obs_wb[prev] - fc_wb[prev] if prev in fc_wb else 0.0   # how wrong the provider was a day ago
        rows.append(wetbulb_row(t, 0, p_wb, T, RH, recent_residual=residual))
        y.append(obs_wb[t]); pers.append(obs_wb[prev]); prov.append(p_wb); test.append(t[:10] >= test_from)
    return rows, y, pers, prov, test


def carbon_dataset(region_id: str, leads=(1, 6, 12, 24)):
    path = ROOT / "data" / "history" / f"{region_id}.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as f:
        real = {r["hour"]: float(r["ci_g_per_kwh"]) for r in csv.DictReader(f) if r["ci_source"] != "modelled"}
    hours = sorted(real)
    if len(hours) < 24 * 10:
        return None
    fmt = "%Y-%m-%dT%H:00"
    test_from = (datetime.strptime(hours[-1], fmt) - timedelta(days=TEST_DAYS)).strftime(fmt)
    rows, y, pers, prov, test = [], [], [], [], []
    for issue in hours:
        for lead in leads:
            target = (datetime.strptime(issue, fmt) + timedelta(hours=lead)).strftime(fmt)
            yday = (datetime.strptime(target, fmt) - timedelta(hours=24)).strftime(fmt)
            if target not in real or yday not in real:
                continue
            rows.append(carbon_row(target, lead, real[issue], real[yday]))
            y.append(real[target]); pers.append(real[issue]); prov.append(real[issue]); test.append(target >= test_from)
    return rows, y, pers, prov, test


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--regions", help="comma-separated (default: all)")
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = args.regions.split(",") if args.regions else list(region_config.load())
    metrics = []
    for rid in wanted:
        region = region_config.get(rid)
        for target, features, data in (("t_wb", WETBULB_FEATURES, lambda: wetbulb_dataset(region, args.days)),
                                       ("ci", CARBON_FEATURES, lambda: carbon_dataset(rid))):
            d = data()
            if d is None:
                print(f"{rid:16} {target:5} skipped: not enough real history yet")
                metrics.append({"region": rid, "target": target, "skipped": "not enough real history"})
                continue
            try:
                rows, y, persistence, provider, test = d
                verdict, model = fit_and_judge(target, rid, rows, y, features, persistence, provider, test)
            except ValueError as e:
                print(f"{rid:16} {target:5} skipped: {e}")
                metrics.append({"region": rid, "target": target, "skipped": str(e)})
                continue
            v = verdict.as_dict()
            metrics.append(v)
            print(f"{rid:16} {target:5} MAE model {v['mae_model']:.3f} | persistence {v['mae_persistence']:.3f} | "
                  f"provider {v['mae_provider']:.3f} -> {'USE' if v['use_model'] else 'not used'}")
            path = OUT / f"{rid}-{target}.json"
            if verdict.use_model:
                path.write_text(json.dumps({**model, "verdict": v}) + "\n")
            elif path.exists():
                path.unlink()
    (OUT / "metrics.json").write_text(json.dumps({
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "test_days": TEST_DAYS, "results": metrics}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
