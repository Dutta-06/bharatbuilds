# Chhaanv

Heat and waterlogging risk, hour by hour, for the people who work outdoors in
Indian cities. Built for Environmental Hacks (Bharat Builds Tour), Heat and Water track.

The build plan is in [`chhaanv-build-plan.md`](chhaanv-build-plan.md), and
[`docs/thresholds.md`](docs/thresholds.md) explains how risk is decided.

## Status

| Step | State |
|---|---|
| 0 Setup | Repo, CI and SAM skeleton done. AWS account, IAM and eligibility are on the team |
| 1 Risk engine | Done: WBGT, heat index, ISO 7243 bands, waterlogging, EN/HI windows, CLI, tests |
| 2+ | Not started |

## Risk engine

Pure Python 3.12, standard library only.

```bash
pip install pytest
python -m pytest

# live forecast from Open-Meteo
python -m engine --lat 28.7 --lon 77.1 --work heavy
python -m engine --lat 28.7 --lon 77.1 --work heavy --lang hi

# offline, using the synthetic Delhi fixture
python -m engine --from-file tests/engine/fixtures/delhi_may_synthetic.json --now 2026-05-26T05:00
```

Options: `--work light|moderate|heavy`, `--lang en|hi`, `--hazard heat|waterlogging|all`,
`--hotspot`, `--unacclimatised`, `--json`.

## Layout

```
engine/            risk engine (no AWS)
  wbgt.py          WBGT estimate (Stull wet bulb + globe heat balance; BoM cross-check)
  heat_index.py    NOAA heat index fallback
  thresholds.py    ISO 7243 bands per work intensity
  waterlogging.py  rain per 3 h x hotspot x elevation
  windows.py       plain-language safe windows
  strings/         all user-facing text (en, hi)
  openmeteo.py     forecast client
  risk.py          combines the above into 48-hour strips
functions/         Lambda handlers (Step 3+)
template.yaml      SAM template
tests/
```
