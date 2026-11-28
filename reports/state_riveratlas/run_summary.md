# NOWRI run summary - mode `state` - river source `riveratlas`

- Run: `state_riveratlas_20261128T045043Z`  |  pipeline 0.1.1  |  commit `None`
- Extraction box (lon/lat): `[4.7268, 4.0202, 7.8406, 6.7512]`
- Total records: **1269**  |  assigned to pilot states: **956**  |  unassigned: **313**
- Direct intersections: **280**  |  unique OGIM IDs: 1245
- Consistency-audit problems: **0**

## Bands (assigned records)

- Intersecting (0 km): 280
- >0–1 km: 460
- 1–5 km: 213
- >5 km: 3

## Records by layer (total / assigned / intersecting)

- pipelines: 140 / 140 / 126
- oil_gas_fields: 177 / 177 / 154
- gas_processing: 6 / 6 / 0
- offshore: 192 / 37 / 0
- terminals: 29 / 26 / 0
- refineries: 3 / 3 / 0
- stations: 237 / 211 / 0
- flaring: 438 / 356 / 0
- wells: 47 / 0 / 0

## Records by state (assigned)

- Bayelsa: 185
- Rivers: 428
- Delta: 343

## Extra layers included: lng

## Change relative to the documented v0.1 baseline (informational)

The extraction extent differs from v0.1 on purpose, so differences are expected (this is not a test). 10 of 41 baseline values are unchanged.

| quantity | v0.1 | now | change |
|---|---:|---:|---:|
| records_by_layer.pipelines | 112 | 140 | +28 |
| records_by_layer.oil_gas_fields | 152 | 177 | +25 |
| records_by_layer.gas_processing | 5 | 6 | +1 |
| records_by_layer.offshore | 124 | 192 | +68 |
| records_by_layer.terminals | 24 | 29 | +5 |
| records_by_layer.refineries | 1 | 3 | +2 |
| records_by_layer.stations | 226 | 237 | +11 |
| records_by_layer.flaring | 361 | 438 | +77 |
| records_by_layer.wells | 27 | 47 | +20 |
| assigned_by_layer.pipelines | 112 | 140 | +28 |
| assigned_by_layer.oil_gas_fields | 152 | 177 | +25 |
| assigned_by_layer.gas_processing | 5 | 6 | +1 |
| assigned_by_layer.offshore | 36 | 37 | +1 |
| assigned_by_layer.terminals | 22 | 26 | +4 |
| assigned_by_layer.refineries | 1 | 3 | +2 |
| assigned_by_layer.stations | 200 | 211 | +11 |
| assigned_by_layer.flaring | 295 | 356 | +61 |
| intersections_by_layer.pipelines | 107 | 126 | +19 |
| intersections_by_layer.oil_gas_fields | 133 | 154 | +21 |
| total_records | 1032 | 1269 | +237 |
| assigned_total | 823 | 956 | +133 |
| unassigned_total | 209 | 313 | +104 |
| intersections_total | 240 | 280 | +40 |
| unique_ogim_ids_total | 1008 | 1245 | +237 |
| bands_assigned.Intersecting (0 km) | 240 | 280 | +40 |
| bands_assigned.>0–1 km | 403 | 460 | +57 |
| bands_assigned.1–5 km | 179 | 213 | +34 |
| bands_assigned.>5 km | 1 | 3 | +2 |
| records_by_state.Rivers | 295 | 428 | +133 |
| river_sections_clipped | 5231 | 5772 | +541 |
| river_unique_ids_clipped | 5069 | 5610 | +541 |

## Projection sensitivity (sample of 79 records, up to 10 per layer)

- tied nearest-river records: 14; zero-distance records: 18; non-zero comparisons: 61
- mean / median / 75th percentile / maximum absolute difference (m): 0.473557 / 0.028606 / 0.137832 / 4.581196
- mean / maximum percentage difference: 0.003206% / 0.013563%
- stored distances matching the recalculation: 79 of 79
- statistics are over the non-zero-distance records only (as in the v0.1 verification)

## Tolerance sensitivity (assigned records: intersecting or within t metres)

| t (m) | records | % |
|---:|---:|---:|
| 0 | 280 | 29.29 |
| 1 | 283 | 29.6 |
| 10 | 290 | 30.33 |
| 50 | 305 | 31.9 |
| 100 | 329 | 34.41 |
| 250 | 421 | 44.04 |
| 500 | 530 | 55.44 |
| 1000 | 740 | 77.41 |

## OGIM layer coverage audit (Nigerian records inside extraction box)

- Crude_Oil_Refineries: 3
- Equipment_and_Components: 0
- Gathering_and_Processing: 6
- Injection_and_Disposal: 0
- LNG_Facilities: 7
- Natural_Gas_Compressor_Stations: 0
- Natural_Gas_Flaring_Detections: 438
- Offshore_Platforms: 192
- Oil_and_Natural_Gas_Basins: 0
- Oil_and_Natural_Gas_Fields: 279
- Oil_and_Natural_Gas_License_Blocks: 0
- Oil_and_Natural_Gas_Pipelines: 140
- Oil_and_Natural_Gas_Production: 0
- Oil_and_Natural_Gas_Wells: 47
- Petroleum_Terminals: 29
- Stations_Other: 237
- Tank_Battery: 0
- ML_Oil_and_Natural_Gas_Well_Pads: 0

## Sources

- Oil and Gas Infrastructure Mapping (OGIM) database v3.0: licence = cc-by-4.0
- HydroATLAS - RiverATLAS (river reach lines) v1.0 (Africa tiles): licence = CC BY 4.0: HydroATLAS is licensed as a Collective Database under CC BY 4.0 per the provider's product page and HydroATLAS Technical Documentation v1.0.1 section 4.1. Individual parts keep their own licences and the original HydroSHEDS/HydroRIVERS licences are unaffected. Contains the same reaches and HYRIV_ID as HydroRIVERS.
- geoBoundaries ADM1 (Nigeria) gbOpen/current: licence = Creative Commons Attribution 4.0 International (CC BY 4.0)
