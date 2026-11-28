> **Provenance note.** This summary was transcribed from the Colab output of run `legacy_riveratlas_20261124T222152Z`
> (cell 6 of the notebook). The manifest and CSV tables of that run were not saved. They are regenerated, with the
> same name, whenever cell 6 is run again.

# NOWRI run summary - mode `legacy` - river source `riveratlas`

- Run: `legacy_riveratlas_20261124T222152Z`  |  pipeline 0.1.1
- Extraction box (lon/lat): `[4.5, 4.0, 7.0, 6.5]`
- Total records: **1032**  |  assigned to pilot states: **823**  |  unassigned: **209**
- Direct intersections: **240**  |  unique OGIM IDs: 1008
- Consistency-audit problems: **0**

## Bands (assigned records)

- Intersecting (0 km): 240
- >0–1 km: 403
- 1–5 km: 179
- >5 km: 1

## Records by layer (total / assigned / intersecting)

- pipelines: 112 / 112 / 107
- oil_gas_fields: 152 / 152 / 133
- gas_processing: 5 / 5 / 0
- offshore: 124 / 36 / 0
- terminals: 24 / 22 / 0
- refineries: 1 / 1 / 0
- stations: 226 / 200 / 0
- flaring: 361 / 295 / 0
- wells: 27 / 0 / 0

## Records by state (assigned)

- Bayelsa: 185
- Rivers: 295
- Delta: 343

## Regression vs documented v0.1 baseline: PASS (41/41 checks passed)

## Tolerance sensitivity (assigned records: intersecting or within t metres)

| t (m) | records | % |
|---:|---:|---:|
| 0 | 240 | 29.16 |
| 1 | 243 | 29.53 |
| 10 | 247 | 30.01 |
| 50 | 262 | 31.83 |
| 100 | 281 | 34.14 |
| 250 | 368 | 44.71 |
| 500 | 465 | 56.5 |
| 1000 | 643 | 78.13 |

## Sources

- Oil and Gas Infrastructure Mapping (OGIM) database v3.0: licence = cc-by-4.0
- HydroATLAS - RiverATLAS (river reach lines) v1.0 (Africa tiles): licence = CC BY 4.0 (provider's product page and HydroATLAS Technical Documentation v1.0.1, section 4.1)
- geoBoundaries ADM1 (Nigeria) gbOpen/current: licence = Creative Commons Attribution 4.0 International (CC BY 4.0)
