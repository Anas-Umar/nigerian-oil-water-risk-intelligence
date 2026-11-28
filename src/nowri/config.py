"""Central configuration and documented baseline for the NOWRI pipeline.

Everything that defines *what* the analysis is (CRS, bands, sources, layer
mapping, v0.1 baseline numbers) lives here so that it can be reviewed in one
place and checked by tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PIPELINE_VERSION = "0.1.1"

# ---------------------------------------------------------------------------
# Spatial reference and study area
# ---------------------------------------------------------------------------
# Custom WGS 84 Azimuthal Equidistant projection centred on the pilot area.
# Do not revert to UTM zone 32N without technical justification (see docs).
ANALYSIS_CRS = (
    "+proj=aeqd +lat_0=5.25 +lon_0=5.75 +datum=WGS84 +units=m +no_defs +type=crs"
)
PILOT_STATES = ("Bayelsa", "Rivers", "Delta")

# v0.1 extraction box (min lon, min lat, max lon, max lat), degrees.
# NOTE: its eastern edge (7.0 E) cuts through Rivers State, whose polygon
# extends to about 7.59 E. It is retained ONLY for the regression run.
LEGACY_BBOX = (4.5, 4.0, 7.0, 6.5)
# Margin added around the state polygons in the corrected ("state") mode.
DEFAULT_MARGIN_DEG = 0.25

# ---------------------------------------------------------------------------
# Distance bands (descriptive reporting categories, NOT risk thresholds)
# ---------------------------------------------------------------------------
BAND_INTERSECT = "Intersecting (0 km)"
BAND_0_1 = ">0\u20131 km"
BAND_1_5 = "1\u20135 km"
BAND_GT5 = ">5 km"
BAND_LABELS = (BAND_INTERSECT, BAND_0_1, BAND_1_5, BAND_GT5)
BAND_EDGES_M = (1000.0, 5000.0)

LOC_ASSIGNED = "Assigned to pilot state"
LOC_UNASSIGNED = "Unassigned / outside pilot states"

# Positional tolerances (metres) used in the tolerance-sensitivity table.
TOLERANCES_M = (0, 1, 10, 50, 100, 250, 500, 1000)

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
OGIM_RECORD_ID = "22835235"
OGIM_VERSION = "v3.0"
OGIM_DOI = "10.5281/zenodo.22835235"
OGIM_FILENAME = "OGIM_v3.0.gpkg"
OGIM_CITATION = (
    "OGIM v3.0, Zenodo, https://doi.org/10.5281/zenodo.22835235 (CC BY 4.0). Method: Omara, M. et al. (2023), "
    "Earth System Science Data 15, 3761, https://doi.org/10.5194/essd-15-3761-2023"
)
OGIM_API_URL = f"https://zenodo.org/api/records/{OGIM_RECORD_ID}"
OGIM_FILE_URL = (
    f"https://zenodo.org/records/{OGIM_RECORD_ID}/files/{OGIM_FILENAME}?download=1"
)
# MD5 reported by the Zenodo API when the v0.1 notebook was run (2026-11-21).
OGIM_MD5_OBSERVED = "99d94e96eefe4d7f561d1a2dbcc1a313"

HYDRORIVERS_URL = (
    "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_af_shp.zip"
)
HYDRORIVERS_SHP = "HydroRIVERS_v10_af.shp"
HYDRORIVERS_CITATION = (
    "Lehner, B., & Grill, G. (2013). Global river hydrography and network "
    "routing: Baseline data and new approaches to study the world's large river "
    "systems. Hydrological Processes, 27(15), 2171-2186. "
    "https://doi.org/10.1002/hyp.9740"
)
# RiverATLAS (HydroATLAS v1.0): contains all HydroRIVERS reaches with the same HYRIV_ID, and the provider
# licenses HydroATLAS as a whole under CC BY 4.0 (hydrosheds.org/products/hydroatlas; Technical Documentation
# v1.0.1 section 4.1). Shapefile download is regional tiles inside one ~2.55 GB zip (Figshare).
RIVER_SOURCES = ("hydrorivers", "riveratlas")
RIVERATLAS_URL = "https://figshare.com/ndownloader/files/20087486"
RIVERATLAS_API_URL = "https://api.figshare.com/v2/file/download/20087486"   # second route to the same file
RIVERATLAS_MIN_BYTES = 1_000_000_000      # the real zip is about 2.55 GB; anything smaller is not the archive
RIVERATLAS_ZIP = "RiverATLAS_v10_shp.zip"
RIVERATLAS_TILE_PATTERN = r"RiverATLAS_v10_af[^/\\]*\.(shp|shx|dbf|prj|cpg)$"
RIVERATLAS_CITATION = (
    "Linke, S. et al. (2019). Global hydro-environmental sub-basin and river reach characteristics at high "
    "spatial resolution. Scientific Data 6: 283. https://doi.org/10.1038/s41597-019-0300-6 ; and "
    "Lehner, B., & Grill, G. (2013), https://doi.org/10.1002/hyp.9740"
)
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM1/"


# ---------------------------------------------------------------------------
# Layer definitions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LayerSpec:
    name: str                 # name in the output GeoPackage
    ogim_layer: str           # layer name inside OGIM_v3.0.gpkg
    kind: str                 # "point" | "line" | "polygon"
    asset_category: str
    unit_type: str
    subtype_column: Optional[str] = None   # OGIM column used for Asset_subtype
    subtype_constant: Optional[str] = None


CORE_LAYERS = (
    LayerSpec("pipelines", "Oil_and_Natural_Gas_Pipelines", "line",
              "Pipeline", "State-specific section", subtype_constant="Pipeline"),
    LayerSpec("oil_gas_fields", "Oil_and_Natural_Gas_Fields", "polygon",
              "Oil and gas field", "State-specific section",
              subtype_column="RESERVOIR_TYPE"),
    LayerSpec("gas_processing", "Gathering_and_Processing", "point",
              "Gas processing", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("offshore", "Offshore_Platforms", "point",
              "Offshore platform", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("terminals", "Petroleum_Terminals", "point",
              "Petroleum terminal", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("refineries", "Crude_Oil_Refineries", "point",
              "Refinery", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("stations", "Stations_Other", "point",
              "Station", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("flaring", "Natural_Gas_Flaring_Detections", "point",
              "Gas flaring detection", "Individual detection",
              subtype_constant="Flaring detection"),
    LayerSpec("wells", "Oil_and_Natural_Gas_Wells", "point",
              "Well", "Individual asset", subtype_column="FAC_TYPE"),
)
CORE_LAYER_NAMES = tuple(s.name for s in CORE_LAYERS)

# Layers that returned zero Nigerian records inside the (truncated) v0.1 box.
# In "state" mode they are re-checked and added automatically if non-empty.
EXTRA_LAYERS = (
    LayerSpec("lng", "LNG_Facilities", "point",
              "LNG facility", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("compressors", "Natural_Gas_Compressor_Stations", "point",
              "Compressor station", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("injection", "Injection_and_Disposal", "point",
              "Injection / disposal", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("tank_batteries", "Tank_Battery", "point",
              "Tank battery", "Individual asset", subtype_column="FAC_TYPE"),
    LayerSpec("equipment", "Equipment_and_Components", "point",
              "Equipment / component", "Individual asset",
              subtype_column="FAC_TYPE"),
)
EXTRA_LAYER_NAMES = tuple(s.name for s in EXTRA_LAYERS)

# ---------------------------------------------------------------------------
# Documented v0.1 baseline (box-limited extraction). Source: release README,
# release manifest and independent re-count of the released GeoPackage.
# ---------------------------------------------------------------------------
BASELINE_V01 = {
    "records_by_layer": {
        "pipelines": 112, "oil_gas_fields": 152, "gas_processing": 5,
        "offshore": 124, "terminals": 24, "refineries": 1,
        "stations": 226, "flaring": 361, "wells": 27,
    },
    "assigned_by_layer": {
        "pipelines": 112, "oil_gas_fields": 152, "gas_processing": 5,
        "offshore": 36, "terminals": 22, "refineries": 1,
        "stations": 200, "flaring": 295, "wells": 0,
    },
    "intersections_by_layer": {
        "pipelines": 107, "oil_gas_fields": 133, "gas_processing": 0,
        "offshore": 0, "terminals": 0, "refineries": 0,
        "stations": 0, "flaring": 0, "wells": 0,
    },
    "total_records": 1032,
    "assigned_total": 823,
    "unassigned_total": 209,
    "intersections_total": 240,
    "bands_assigned": {
        BAND_INTERSECT: 240, BAND_0_1: 403, BAND_1_5: 179, BAND_GT5: 1,
    },
    "records_by_state": {"Bayelsa": 185, "Rivers": 295, "Delta": 343},
    "unique_ogim_ids_total": 1008,
    "river_sections_clipped": 5231,
    "river_unique_ids_clipped": 5069,
}
