# NOWRI - Nigerian Oil-Water Risk Intelligence

[![tests](https://github.com/Anas-Umar/nigerian-oil-water-risk-intelligence/actions/workflows/tests.yml/badge.svg)](https://github.com/Anas-Umar/nigerian-oil-water-risk-intelligence/actions)

An independent, founder-led, pilot-stage research project that builds a reproducible geospatial
screening workflow relating oil and gas infrastructure to mapped river networks in Bayelsa, Rivers
and Delta States, Niger Delta, Nigeria.

> **What this is not.** NOWRI is not a registered company, regulator, accredited laboratory or
> validated pollution-monitoring system. Proximity does not establish exposure; exposure does not
> establish contamination; a geometric intersection is not evidence of a physical crossing, a leak or
> unsafe water. Outputs are preliminary screening quantities, not risk assessments.

## Status

| Version | What it is | State |
|---|---|---|
| v0.1 | Scripted GIS screening prototype (notebook, released 2026-11-22) | Documented baseline. Its extraction box stops at 7.0 E, which cuts off eastern Rivers State. |
| v0.1.1 | Modular, tested pipeline with corrected extent and a regression test against v0.1 | This code. First results below (2026-11-24); full reports in `reports/`. |

**Documented v0.1 baseline (box-limited, not the full three states):** 1,032 infrastructure records in
9 categories (823 assigned to the three states, 209 outside the polygons), 5,231 clipped river
sections, 240 direct geometric intersections.

## First results (2026-11-24)

River network: RiverATLAS (HydroATLAS v1.0), which the provider licenses CC BY 4.0 and which contains the same river
reaches as HydroRIVERS. Runs with HydroRIVERS gave identical record counts, river-section counts and tolerance tables,
so RiverATLAS is the default (see `DATA_POLICY.md`).

**Regression.** With the original v0.1 box the pipeline reproduces the documented v0.1 baseline: 41 of 41 checks pass
(`reports/legacy_riveratlas/run_summary.md`, transcribed from the run output; see the note at the top of that file). In an earlier run all 1,032 records also matched the released v0.1 GeoPackage one by one.

**Corrected extent.** The extraction box is taken from the state polygons plus 0.25 degrees
(`reports/state_riveratlas/`). Only Rivers State changes, as expected from the extent error; the Bayelsa and Delta
counts are unchanged.

| | v0.1 box | corrected |
|---|---:|---:|
| Infrastructure records (9 categories) | 1,032 | 1,269 |
| Assigned to Bayelsa, Rivers or Delta | 823 | 956 |
| of which Bayelsa / Rivers / Delta | 185 / 295 / 343 | 185 / 428 / 343 |
| Direct geometric intersections | 240 (29.2% of assigned) | 280 (29.3% of assigned) |
| of which pipeline sections / field sections | 107 / 133 | 126 / 154 |
| Clipped river sections | 5,231 | 5,772 |
| Refineries | 1 | 3 |
| LNG facilities (previously outside the box) | 0 | 7 |
| Wells (none assigned to a state in either run) | 27 | 47 |

The share of assigned records that directly intersect a mapped river is almost unchanged (29.2% to 29.3%), so
the headline share looks stable across these two extents, although the counts differ. Intersection is a geometric
screening flag only; it is sensitive to positional tolerance (for example 421 of 956 assigned records are
intersecting or within 250 m) and says nothing about contamination or exposure.

## Quick start

Google Colab (recommended): open `notebooks/NOWRI_run_in_colab.ipynb` and follow the cells.

Local:

```bash
pip install -r requirements-dev.txt
pip install -e .                         # makes `python -m nowri` available
python -m pytest -q                      # unit + geometry tests
python -m nowri check-env
python -m nowri run --mode legacy        # regression: must reproduce the v0.1 baseline
python -m nowri run --mode state         # corrected extent (river data: RiverATLAS, CC BY 4.0)
```

The first run downloads OGIM v3.0 (about 3.4 GB), RiverATLAS (about 2.5 GB zip; if the automatic download is blocked use
`--riveratlas-zip`) and the state boundaries into `data/raw/` (git-ignored) and verifies the OGIM checksum.

## Run modes

- `legacy` uses the original v0.1 box. It must reproduce the documented numbers; exit code 2 means it did not.
- `--river-source riveratlas` (the default) takes the river network from RiverATLAS (same reaches as HydroRIVERS, CC BY 4.0
  per the provider); `--river-source hydrorivers` uses HydroRIVERS under its stricter licence. Reports go to
  `reports/<mode>_<river source>/` (for example `reports/state_riveratlas/`).
- `state` takes the box from the three state polygons plus a margin and also audits every OGIM layer in the
  box, adding any previously empty layer that now has Nigerian records (for example LNG facilities).

## Outputs

`outputs/<run>/` (git-ignored): GeoPackage (EPSG:4326), full data dictionary, manifest, log.
`reports/<mode>_<river source>/` (committable aggregates): run summary, figures, projection-sensitivity check, manifest with software versions and source
licences, tolerance-sensitivity and network-sensitivity tables, layer-coverage audit, data dictionary
without example values.

## Repository layout

```
src/nowri/      pipeline code (config, sources, pipeline, proximity, qc, release, cli)
tests/          unit tests (pure logic) and geometry tests (need geopandas)
tools/          data-policy checker and pre-commit hook
docs/           METHOD.md, RUNBOOK.md
metadata/       dataset register
reports/        aggregate run reports
notebooks/      Colab runner (stored without outputs)
```

## Data policy

No third-party data are stored here. OGIM and geoBoundaries are CC BY 4.0; RiverATLAS is CC BY 4.0 per the
provider; HydroRIVERS is under the HydroSHEDS licence, which prohibits stand-alone redistribution. See [DATA_POLICY.md](DATA_POLICY.md),
[ATTRIBUTION.md](ATTRIBUTION.md) and [metadata/dataset_register.csv](metadata/dataset_register.csv).

## Known limitations

See [docs/METHOD.md](docs/METHOD.md). In brief: coarse river data, no hydrological connectivity, patchy
OGIM attributes (status and operator are largely `N/A`), and distances to a river network clipped to the
state polygons.

## Citation and licence

See `CITATION.cff`. Source code: MIT (see `LICENSE`). The licence applies to the code only; third-party
datasets keep their own licences.
