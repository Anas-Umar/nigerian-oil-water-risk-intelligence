# Data policy

**This repository contains code, documentation and aggregate reports only. It does not contain third-party
datasets or record-level data derived from them.**

## Licences (checked)

| Dataset | Licence | What it requires | In this repository? |
|---|---|---|---|
| OGIM v3.0 (Zenodo 10.5281/zenodo.22835235) | **CC BY 4.0** (confirmed on the Zenodo record; also recorded from the Zenodo API in every run manifest) | Credit the creators, link to the licence, indicate changes. Redistribution and adaptation are allowed. | No |
| geoBoundaries ADM1 Nigeria (GRID3-sourced) | **CC BY 4.0** (as returned by the geoBoundaries API; recorded in every run manifest) | Same as above | No |
| RiverATLAS (HydroATLAS v1.0): the same river reaches and `HYRIV_ID` as HydroRIVERS | **CC BY 4.0**, stated by the provider for HydroATLAS as a whole | Credit (Linke et al. 2019), link the licence, indicate changes. | No |
| HydroRIVERS v1.0 Africa (HydroSHEDS version 1 licence, Technical Documentation v1.4, Appendix A) | Custom licence: free for non-commercial and commercial use | Stand-alone redistribution of the licensed data is prohibited. Distributing it incorporated in a derived product to end users requires an end-user licence at least as protective and the mandatory attribution notice (Exhibit B). | No |

Not legal advice. Read the licences themselves before releasing anything.

## Choosing the river source

The pipeline can take the river network from either product:

- `--river-source riveratlas` (the default) uses RiverATLAS, which the provider licenses CC BY 4.0. **Use this for
  anything that will be published or shared.**
- `--river-source hydrorivers` (used for the original v0.1) applies the stricter HydroSHEDS version 1 licence described
  above.

Verified on 2026-11-24: the `legacy` regression with RiverATLAS passed all 41 baseline checks, and every aggregate
output of both the `legacy` and `state` runs was identical to the corresponding HydroRIVERS run: record counts, river
sections inside the box (7,114 and 11,126 records; 5,231 and 5,772 clipped sections) and all eight tolerance counts,
which depend on metre-level positions. So the river geometry and IDs in the study area are effectively identical.
(A record-by-record comparison was made earlier with HydroRIVERS only.)

What the provider says about HydroATLAS (Technical Documentation v1.0.1, section 4.1): it is a *Collective Database*
licensed as a whole under CC BY 4.0, its individual parts remain governed by their own licences, and the licences of the
underlying source datasets in their original form are not changed. So the residual uncertainty is small but not zero:
the river lines and the pre-existing HydroRIVERS columns are not discussed separately in that section. The HydroSHEDS
team is the only authority on that point. Practice supports this reading: the same team publishes the reaches under
CC BY 4.0 in HydroATLAS, and HydroSHEDS v2 core products are CC BY 4.0 (currently for the Americas only).

Not legal advice.

## What may be committed

Source code, tests, documentation, metadata registers, and `reports/` (aggregate counts, manifests, sensitivity
tables, a data dictionary without example values).

## What must not be committed

`data/`, `outputs/`, `archive/`, any `.gpkg`, `.shp`, `.geojson`, `.tif`, `.zip`, `.parquet` and similar.
Notebooks are committed with outputs cleared. Enforced by `.gitignore`, `tools/check_no_data.py` (also in CI,
and run by the notebook before every upload) and an optional pre-commit hook.

**Never publish HydroRIVERS itself in any form** (original files, clipped extracts, converted copies).

## Why the derived GeoPackage is still not in git

Even though OGIM and geoBoundaries permit redistribution, a record-level GeoPackage belongs in a citable archive
(for example Zenodo), not in git history, and one open point remains for HydroRIVERS-based runs: the output contains no river
geometries and no river identifiers (only distances, flags and a count of tied reaches), but whether publishing such
derived attributes is allowed under the HydroSHEDS version 1 licence has not been confirmed by the provider. The
RiverATLAS option avoids the question.

## Checklist before releasing the derived dataset

1. Produce the dataset with the default `--river-source riveratlas` after the `legacy` regression has passed. (If you used
   `hydrorivers` instead, you additionally need the HydroSHEDS licensor's confirmation that publishing derived
   distance attributes without river geometries is acceptable, and the exact Exhibit B attribution text from page 29 of
   the HydroSHEDS Technical Documentation v1.4 in the dataset's README and metadata.)
2. Credit OGIM, geoBoundaries and HydroATLAS/RiverATLAS (see `ATTRIBUTION.md`), link the CC BY 4.0 licence, and state
   what was changed (clipped, projected, spatially joined, derived fields added).
3. Check that the dataset contains no river geometries (the pipeline does not write any).
4. Describe it as a preliminary screening dataset with no warranty.
5. Release through Zenodo, not git.

## If data is committed by mistake

Deleting the file in a new commit is not enough, because history keeps it. Make the repository private, remove the
data from history (`git filter-repo`) or recreate the repository from a clean tree, and check for forks.
