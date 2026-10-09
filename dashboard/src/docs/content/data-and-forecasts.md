# Data and forecasts

## Where the inputs come from

| Input | Source | Refreshed |
|---|---|---|
| Air temperature, humidity, pressure for the next 48 hours | [Open-Meteo](https://open-meteo.com) | Every hour |
| Grid carbon intensity forecast and generation mix | [Electricity Maps](https://www.electricitymaps.com) | Every hour |
| Cooling curves, water factors, GPU power | Published sources listed in the project's `coefficients.yaml` | When the model is updated |

The header shows when the forecast pipeline last ran, for example `forecast 18:05 (38 min ago)`. The light is green when the data is under 90 minutes old, amber when it is older or when any region is using modelled carbon, and red after three hours.

## Source labels

Every forecast row records where each value came from. The **Forecasts** page shows these labels.

| Label | Meaning |
|---|---|
| `open-meteo` | Weather from Open-Meteo. |
| `synthetic` | Generated offline for testing. Not a forecast. A warning banner appears if any region uses it. |
| `electricitymaps-forecast` | Carbon intensity from Electricity Maps' own forecast. |
| `electricitymaps-latest-held` | Electricity Maps forecasts only part of the 48 hours. Past its horizon the latest value is held constant. |
| `modelled` | A typical daily carbon profile, used only when no Electricity Maps data is available. A warning banner appears. |
| `provider` (wet-bulb) | The wet-bulb temperature worked out from Open-Meteo's forecast. |
| `model` (wet-bulb) | A trained correction that replaced the provider value. |

## Trained models

Tidewise can learn the systematic error of a provider's forecast. A gradient-boosted model is trained per region and kept **only if it beats both baselines on a held-out week**:

1. **Persistence**, which repeats yesterday's value;
2. the **provider's own forecast**.

A model that does not beat both is not used, and the Forecasts page shows `provider` for that region. This is deliberate: the system only uses a model that has proved itself. Today two regions, Stockholm and Frankfurt, use a trained wet-bulb model. Carbon models need about ten days of collected history, and are not in use yet.

## Forecast error

The Forecasts page shows the last run's error: the previous run's prediction compared with the new run's first three hours. This is a stand-in for real observations. A value near zero means forecasts have been stable, not necessarily accurate.

## Forecast history

A scheduled job saves each region's real carbon and weather hours to storage every six hours. The history is used to train carbon models and to replace placeholder grid mixes with real averages.
