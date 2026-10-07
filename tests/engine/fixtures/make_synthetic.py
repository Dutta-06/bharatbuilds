"""Regenerate delhi_may_synthetic.json: a SYNTHETIC Open-Meteo-shaped forecast.

Shaped after a typical late-May Delhi pattern (dry heat, 30 °C nights, 44 °C
afternoons, RH 15-45 %) with a pre-monsoon thunderstorm on the second evening.
It is test data, not observations.

    python tests/engine/fixtures/make_synthetic.py
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("delhi_may_synthetic.json")
DAY0 = datetime(2026, 5, 26)
PAST_HOURS = 6
STORM = {18: 4.0, 19: 18.0, 20: 22.0, 21: 6.0}  # mm per hour, second evening


def main() -> None:
    hourly = {k: [] for k in ("time", "temperature_2m", "relative_humidity_2m",
                              "shortwave_radiation", "wind_speed_10m", "precipitation")}
    for i in range(72 + PAST_HOURS):
        t = DAY0 + timedelta(hours=i - PAST_HOURS)
        h, day = t.hour, (t.date() - DAY0.date()).days
        phase = math.cos((h - 15) / 24 * 2 * math.pi)  # 1 at 3 PM, -1 at 3 AM
        temp = 37 + 7 * phase
        rh = 30 - 15 * phase
        sw = max(0.0, 950 * math.sin((h - 6) / 13 * math.pi)) if 6 <= h <= 19 else 0.0
        wind = 2.5 + 1.5 * math.sin((h - 9) / 24 * 2 * math.pi)
        rain = 0.0
        if day == 1 and h in STORM:
            rain = STORM[h]
            temp, rh, sw, wind = temp - 8, rh + 40, sw * 0.2, wind + 4
        elif day == 1 and h in (22, 23):
            temp, rh = temp - 6, rh + 30
        hourly["time"].append(t.strftime("%Y-%m-%dT%H:%M"))
        hourly["temperature_2m"].append(round(temp, 1))
        hourly["relative_humidity_2m"].append(int(min(rh, 98)))
        hourly["shortwave_radiation"].append(round(sw, 1))
        hourly["wind_speed_10m"].append(round(wind, 2))
        hourly["precipitation"].append(rain)

    OUT.write_text(json.dumps({
        "_note": "SYNTHETIC test fixture shaped like an Open-Meteo /v1/forecast response. "
                 "Not real data. Regenerate with make_synthetic.py.",
        "latitude": 28.7, "longitude": 77.1, "elevation": 214.0,
        "utc_offset_seconds": 19800, "timezone": "Asia/Kolkata",
        "hourly_units": {"temperature_2m": "°C", "relative_humidity_2m": "%",
                         "shortwave_radiation": "W/m²", "wind_speed_10m": "m/s",
                         "precipitation": "mm"},
        "hourly": hourly,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
