# Method (v0.1.1)

NOWRI is a **preliminary spatial screening** workflow. Proximity does not establish exposure,
exposure does not establish contamination, and a geometric intersection is not evidence of a physical
crossing, a leak or unsafe water.

## Inputs

OGIM v3.0 (infrastructure), HydroRIVERS v1.0 Africa (rivers), geoBoundaries ADM1 (state polygons).
See `metadata/dataset_register.csv` and `DATA_POLICY.md`.

## Steps

1. **Study area.** Pilot states: Bayelsa, Rivers, Delta (geoBoundaries `shapeName`).
   - `legacy` mode: box (4.5, 4.0, 7.0, 6.5) degrees, as in v0.1.
   - `state` mode: bounds of the three polygons plus 0.25 degrees.
2. **Infrastructure.** For each OGIM layer, features whose envelope intersects the box, Nigerian records only.
   Lines are clipped to the box and then to each state; polygons are clipped to each state
   (state-specific sections, so one asset can yield several records). Points are assigned with a
   `within` join; points outside the three polygons are kept and labelled unassigned.
3. **Rivers.** HydroRIVERS inside the box, clipped to the state polygons.
4. **Projection.** Custom WGS 84 azimuthal equidistant projection centred on 5.25 N, 5.75 E
   (`+proj=aeqd +lat_0=5.25 +lon_0=5.75 +datum=WGS84 +units=m +no_defs`).
5. **Proximity.** Minimum planar geometry-to-geometry distance (unrounded metres) to the clipped
   river network; ties are counted by distinct `HYRIV_ID`. The intersection flag is a geometric
   `intersects` test.
6. **Bands** (descriptive, not risk thresholds): Intersecting (0 km); >0-1 km; 1-5 km; >5 km,
   from unrounded distance.
7. **Quality control.** Consistency audit of flags, distances and bands for every record;
   regression comparison with the documented v0.1 baseline; placeholder counts
   (`N/A`, -999, 1900-01-01, nulls).
8. **Projection check.** A reproducible sample of up to 10 records per layer (seed 42): the nearest river is found in
   the AEQD projection (ties kept), the nearest-point pair is converted back to geographic coordinates and its WGS 84
   ellipsoidal length is compared with the projected distance. Statistics are over the non-zero records only. This checks
   projection distortion; it does not prove the projected pair is the globally nearest pair.
9. **Figures.** Proximity bands by infrastructure type, proximity bands by state, and a study-area map are drawn into
   `reports/<mode>_<river source>/figures/` (colour-blind-safe palette, data sources credited on each figure).
10. **Sensitivity.** Counts of records intersecting or within t metres; and results against the unclipped
   river network.

## Interpretation limits

- HydroRIVERS derives from 15 arc-second data: coarse positions and many small channels are absent.
- Distances for records outside the state polygons are to the clipped network only.
- Intersection rates for polygons, lines and points are not comparable (larger geometries intersect
  a dense network more often).
- OGIM attributes such as status and operator are largely `N/A`; in the v0.1 extent all 27 wells fall outside the three state polygons (their coordinates suggest offshore) and no onshore wells appear.
- No hydrological connectivity, terrain, tides or water-quality data are used.
