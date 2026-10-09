# Regions

Tidewise can place jobs in eight AWS regions.

| Region | Location | Jurisdiction | Cooling model |
|---|---|---|---|
| `ap-south-1` | Mumbai | India | Cooling towers |
| `ap-south-2` | Hyderabad | India | Cooling towers |
| `ap-southeast-1` | Singapore | Singapore | Cooling towers |
| `eu-north-1` | Stockholm | EU | Direct evaporative |
| `eu-west-1` | Ireland | EU | Direct evaporative |
| `eu-central-1` | Frankfurt | EU | Direct evaporative |
| `us-east-1` | N. Virginia | US | Direct evaporative |
| `us-west-2` | Oregon | US | Direct evaporative |

The live list, with coordinates and model details, comes from `GET /regions`.

## What the cooling model means

AWS describes direct evaporative cooling for most regions. In hot, humid places where that cannot work all year, Tidewise assumes chilled water with cooling towers, which use more water. This is a modelling assumption, since AWS does not publish the cooling design of each site. See [Water and carbon](#/docs/water-and-carbon).

## Locations are approximate

Weather comes from the metro area each region is named after, not from the data centre site, because AWS does not publish site locations.

## Residency

With **data residency** on, a job stays in the same jurisdiction as its submit region. The EU group covers Stockholm, Ireland and Frankfurt. The two India regions form one group. See [Policies](#/docs/guide-policies).

## Grid and water-stress data

Each region's grid mix sets how much water the electricity itself uses. Some values are still marked as placeholders in the region file until annual data is imported. The **Forecasts** page shows which regions use trained models and which use fallback methods. See [Data and forecasts](#/docs/data-and-forecasts).
