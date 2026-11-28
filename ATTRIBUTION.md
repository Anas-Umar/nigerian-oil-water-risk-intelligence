# Attribution

NOWRI code is MIT-licensed. The analysis uses these third-party datasets (not redistributed here).

## OGIM (Oil and Gas Infrastructure Mapping), CC BY 4.0
OGIM v3.0, Zenodo, https://doi.org/10.5281/zenodo.22835235.
Method paper: Omara, M. et al. (2023), Earth System Science Data 15, 3761, https://doi.org/10.5194/essd-15-3761-2023.
Licence: https://creativecommons.org/licenses/by/4.0/
Changes made by NOWRI: filtered to Nigerian records inside the extraction box, lines and polygons clipped to the
pilot states, projected, and joined to derived proximity fields. No endorsement by the OGIM authors is implied.

## geoBoundaries ADM1 (Nigeria), CC BY 4.0
geoBoundaries (gbOpen), Nigeria ADM1 as returned by the geoBoundaries API (source: GRID3). The exact source, year
and licence of each run are in `reports/<mode>/run_manifest.json`.
Licence: https://creativecommons.org/licenses/by/4.0/

## HydroATLAS / RiverATLAS v1.0, CC BY 4.0 (when `--river-source riveratlas` is used)
Linke, S. et al. (2019). Global hydro-environmental sub-basin and river reach characteristics at high spatial
resolution. Scientific Data 6: 283. https://doi.org/10.1038/s41597-019-0300-6. Data: https://www.hydrosheds.org/hydroatlas
Licence: https://creativecommons.org/licenses/by/4.0/ (HydroATLAS Technical Documentation v1.0.1, section 4.1).
Changes made by NOWRI: reaches clipped to the pilot states and used to compute distances and intersection flags; no river
geometries are redistributed. Cite Lehner & Grill (2013) as well.

## HydroRIVERS / HydroSHEDS version 1, WWF (when `--river-source hydrorivers` is used)
Lehner, B., Grill, G. (2013). Global river hydrography and network routing. Hydrological Processes 27(15),
2171-2186. https://doi.org/10.1002/hyp.9740. Data: https://www.hydrosheds.org

The HydroSHEDS licence (Technical Documentation v1.4, Appendix A) requires a specific copyright and no-warranty
notice (Exhibit B, page 29) to accompany any derived product provided to end users. **Before any derived dataset is
released, copy that notice verbatim from Exhibit B into the dataset's README and metadata.** The wording is not
reproduced here so that it is taken from the source.

Short form for reports and papers: "This work uses HydroRIVERS (HydroSHEDS version 1), (c) World Wildlife Fund,
Inc., used under licence. WWF has not evaluated the data as altered and gives no warranty."
