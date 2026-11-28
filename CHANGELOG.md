# Changelog

## 0.1.1 - 2026-11-24

- First runs: the `legacy` regression passed (41/41 checks; all 1,032 records matched the released v0.1 GeoPackage).
  The corrected extent gives 1,269 records (956 assigned; Rivers 295 to 428), 280 direct intersections (29.3% of assigned),
  and adds 7 LNG facilities and 2 more refineries. See `reports/`.
- State-mode reports now describe differences from v0.1 as informational rather than as a failed test.
- New option `--river-source riveratlas`, now the default: RiverATLAS (HydroATLAS) contains the same reaches and IDs as
  HydroRIVERS and is licensed CC BY 4.0 by the provider. Verified 2026-11-24: the legacy regression passes 41/41 and all
  aggregate outputs (including the tolerance tables) are identical to the HydroRIVERS runs.
- Every run now also performs the projection-sensitivity check (the v0.1 verification) and draws the three paper figures
  (`figures/` in each report folder). Both are guarded so that a failure cannot affect the analysis.
- Downloads are validated (a web page instead of a zip is rejected with a clear message), with a second download route and
  a `--riveratlas-zip` option for a manually obtained file.
- Data policy updated: OGIM and geoBoundaries confirmed CC BY 4.0; HydroSHEDS licence terms summarised;
  `ATTRIBUTION.md` added.

- Replaced the 401-cell working notebook with a modular, tested pipeline (`src/nowri`).
- Two run modes: `legacy` reproduces the documented v0.1 numbers with the original box
  (regression test); `state` takes the extraction box from the state polygons.
- Fixed the extent problem found in the v0.1 audit: the v0.1 extraction box stopped at
  7.0 E while the state polygons extend to about 7.59 E, which cut off eastern Rivers State
  (infrastructure and rivers).
- Intersection is a geometric `intersects` test; bands use unrounded distances
  (root cause of the two-station misclassification in v0.1 was rounding to 3 decimals).
- OGIM is downloaded locally and verified by MD5 (remote reads were unreliable in v0.1);
  the Zenodo licence field is recorded in every manifest.
- Added tolerance-sensitivity and clipped-versus-unclipped-network sensitivity tables,
  an audit of all OGIM layers in the extraction box, and a state-attribute-conflict flag.
- Data dictionary now describes every field (v0.1: 237 of 255 descriptions were empty).
- Output GeoPackage is stored in EPSG:4326 (v0.1 used an unnamed custom SRS); distances are
  still computed in the custom AEQD projection.
- Repository hygiene: strict `.gitignore`, data-policy checker, CI, MIT licence for code.

## 0.1 - 2026-11-22 (baseline, documented)

- 9 infrastructure categories, 1,032 records (823 assigned to Bayelsa, Rivers or Delta; 209 outside the
  three polygons), 5,231 clipped river sections, 240 direct intersections.
- Extraction box 4.5-7.0 E, 4.0-6.5 N (truncates eastern Rivers State; see 0.1.1).
