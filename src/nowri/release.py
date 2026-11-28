"""Release artefacts: checksums, data dictionary, manifest and run summary."""
from __future__ import annotations

import datetime as _dt
import hashlib
import platform
import re
import subprocess
from typing import Dict, Iterable, List, Mapping, Optional

import pandas as pd

from .config import BAND_LABELS, PIPELINE_VERSION

LIMITATIONS = [
    "Preliminary spatial screening only; not a validated environmental risk assessment.",
    "Proximity or geometric intersection does not establish exposure, contamination, "
    "leakage, a physical pipeline crossing or unsafe water.",
    "Hydrological connectivity is not modelled; no flow direction, terrain or tidal effects.",
    "HydroRIVERS (derived from 15 arc-second data) omits many small creeks and channels "
    "and has coarse positional accuracy relative to the infrastructure data.",
    "OGIM coverage, attributes, dates and positions may be incomplete, generalised or out of date. "
    "Status and operator attributes are largely 'N/A'.",
    "Distances for records outside the three pilot-state polygons are measured to a river "
    "network clipped to those polygons and must not be read as distances to all Nigerian rivers.",
    "Distances are measured to a river network clipped to the state polygons; see "
    "network_sensitivity.csv for the effect of using the unclipped network.",
    "Satellite flaring detections are not measurements of water contamination.",
    "Distance bands are descriptive categories, not regulatory limits or validated risk classes.",
]

DERIVED_FIELD_DESCRIPTIONS: Dict[str, str] = {
    "SPATIAL_STATE": "Pilot state (Bayelsa, Rivers or Delta) from a spatial join of the feature to "
                     "geoBoundaries ADM1 polygons ('within' for points; clipping for lines and polygons). "
                     "Empty if the feature lies outside the three state polygons.",
    "Location_assignment": "Whether the record was assigned to a pilot state or lies outside the three state polygons.",
    "Asset_category": "NOWRI asset category (one per output layer).",
    "Unit_type": "'State-specific section' for lines/polygons clipped to a state (one asset may appear in "
                 "several records); otherwise an individual asset or detection.",
    "Asset_subtype": "Sub-type taken from the OGIM facility/reservoir type where available.",
    "Section_ID": "Identifier of the state-specific section within its layer (assigned by NOWRI).",
    "CLIPPED_LENGTH_KM": "Geodesic (WGS 84) length in km of the section after clipping to the state.",
    "CLIPPED_AREA_KM2": "Geodesic (WGS 84) area in km2 of the polygon section after clipping to the state.",
    "State_attribute_conflict": "True if the OGIM STATE_PROV attribute disagrees with SPATIAL_STATE "
                                "(assigned point records with a usable source state only).",
    "Source_state": "State name as given in the OGIM STATE_PROV attribute (may disagree with SPATIAL_STATE).",
    "Distance_to_river_m": "Minimum planar geometry-to-geometry distance in metres, in the custom AEQD "
                           "projection, to the state-clipped river network (HydroRIVERS / RiverATLAS reaches). Unrounded. 0 if intersecting.",
    "Distance_to_river_km": "Distance_to_river_m / 1000 rounded to 3 decimals. Display only; never used to classify.",
    "Nearest_river_matches": "Number of distinct HYRIV_ID values tied at the minimum distance.",
    "Intersects_mapped_river": "True if the geometry directly intersects a clipped HydroRIVERS geometry "
                               "(geometric test, independent of any rounded distance).",
    "Distance_band": "Descriptive band for state-assigned records only: Intersecting (0 km), >0-1 km, "
                     "1-5 km, >5 km. Empty for unassigned records.",
    "Distance_band_to_pilot_network": "Same bands for all records, relative to the state-clipped river network. "
                                      "For unassigned records this is not comparable with assigned results.",
    "Distance_to_unclipped_network_m": "Sensitivity field: minimum distance in metres to the unclipped "
                                       "HydroRIVERS network inside the extraction box.",
    "Intersects_unclipped_network": "Sensitivity field: intersection with the unclipped network.",
}


def describe_field(field: str) -> str:
    if field in DERIVED_FIELD_DESCRIPTIONS:
        return DERIVED_FIELD_DESCRIPTIONS[field]
    if re.fullmatch(r"MMCF_\d{4}", field):
        return f"OGIM source attribute: flaring volume estimate for {field[-4:]} (million cubic feet). See OGIM documentation."
    if field in ("LATITUDE", "LONGITUDE"):
        return f"OGIM source attribute: {field.lower()} in decimal degrees (WGS 84)."
    return "OGIM v3.0 source attribute (see OGIM documentation). The literal string 'N/A' means not available in the source."


# ---------------------------------------------------------------------------
def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def git_commit(cwd: Optional[str] = None) -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def collect_versions() -> Dict[str, Optional[str]]:
    """Versions of the software that produced a run (None if unavailable)."""
    v: Dict[str, Optional[str]] = {"python": platform.python_version(), "platform": platform.platform()}

    def ver(mod, attr="__version__"):
        try:
            m = __import__(mod)
            return getattr(m, attr, None)
        except Exception:
            return None

    for mod in ("geopandas", "pandas", "numpy", "shapely", "pyproj", "pyogrio", "requests"):
        v[mod] = ver(mod)
    try:
        import shapely
        v["geos"] = getattr(shapely, "geos_version_string", None)
    except Exception:
        v["geos"] = None
    try:
        import pyproj
        v["proj"] = getattr(pyproj, "proj_version_str", None)
    except Exception:
        v["proj"] = None
    try:
        import pyogrio
        v["gdal"] = getattr(pyogrio, "__gdal_version_string__", None)
    except Exception:
        v["gdal"] = None
    return v


# ---------------------------------------------------------------------------
def build_data_dictionary(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per layer/field with completeness, placeholders and a description."""
    rows: List[dict] = []
    for layer, df in tables.items():
        n = len(df)
        for col in df.columns:
            if col == "geometry":
                continue
            s = df[col]
            non_null = int(s.notna().sum())
            if pd.api.types.is_numeric_dtype(s):
                na_lit = 0
                m999 = int((s == -999).sum())
                d1900 = 0
            else:
                ss = s.dropna().astype(str).str.strip()
                na_lit = int((ss.str.upper() == "N/A").sum())
                m999 = 0
                d1900 = int(ss.str.startswith("1900-01-01").sum())
            placeholder = na_lit + m999 + d1900
            vals = s.dropna()
            if not pd.api.types.is_numeric_dtype(s):
                vals = vals[~vals.astype(str).str.strip().str.upper().isin(["N/A", ""])]
            examples = " | ".join(map(str, pd.unique(vals)[:3]))
            rows.append({
                "Layer": layer, "Field": col, "Data_type": str(s.dtype),
                "Total_records": n, "Non_null_values": non_null,
                "Null_values": n - non_null,
                "Placeholder_values": placeholder,
                "Informative_values": max(non_null - placeholder, 0),
                "Example_values": examples,
                "Description": describe_field(col),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def build_manifest(*, run_id: str, mode: str, bbox, margin_deg, analysis_crs: str,
                   sources: List[dict], outputs: List[dict], summary: dict,
                   audit_problems: int, river_source: str = "hydrorivers", regression: Optional[dict] = None,
                   record_level: Optional[dict] = None, extra_layers: Optional[List[str]] = None,
                   placeholders: Optional[dict] = None, versions: Optional[dict] = None,
                   commit: Optional[str] = None, projection_check: Optional[dict] = None) -> dict:
    extra_layers = extra_layers or []
    placeholders = placeholders or {}
    versions = versions or {}
    return {
        "project": "Nigerian Oil-Water Risk Intelligence (NOWRI)",
        "pipeline_version": PIPELINE_VERSION,
        "run_id": run_id,
        "mode": mode,
        "created_utc": utc_now_iso(),
        "git_commit": commit,
        "status": "Preliminary spatial screening dataset (not validated)",
        "parameters": {
            "extraction_bbox_lon_lat": list(bbox),
            "state_bounds_margin_deg": margin_deg if mode == "state" else None,
            "river_source": river_source,
            "analysis_crs_proj4": analysis_crs,
            "distance_method": "minimum 2-D planar geometry-to-geometry distance (unrounded metres)",
            "intersection_method": "geometric intersects test",
            "bands": list(BAND_LABELS),
        },
        "sources": sources,
        "outputs": outputs,
        "results": summary,
        "extra_layers_included": extra_layers,
        "quality_control": {
            "consistency_audit_problems": audit_problems,
            **placeholders,
        },
        "projection_check": projection_check,
        "regression_vs_v0_1": regression,
        "record_level_regression_vs_v0_1": record_level,
        "software_environment": versions,
        "limitations": LIMITATIONS,
        "redistribution_note": (
            "This output contains attributes and geometries derived from third-party datasets. OGIM and "
            "geoBoundaries are CC BY 4.0 (attribution required, changes must be indicated). "
            + ("The river network came from RiverATLAS (HydroATLAS), which the provider licenses CC BY 4.0 as a "
               "Collective Database (individual parts keep their own licences; see HydroATLAS Technical "
               "Documentation section 4.1). No river geometries are included in the output. "
               if river_source == "riveratlas" else
               "The distances and flags derive from HydroRIVERS, whose HydroSHEDS licence prohibits stand-alone "
               "redistribution of the river data and requires its mandatory attribution notice; whether derived "
               "distance attributes may be published has not been confirmed with the provider. ")
            + "See DATA_POLICY.md and ATTRIBUTION.md. Only aggregate reports are intended for version control."
        ),
    }


def render_run_summary(manifest: dict, checks: Optional[List[dict]],
                       record_level: Optional[dict], tolerance: Optional[pd.DataFrame],
                       coverage: Optional[pd.DataFrame]) -> str:
    """Plain-markdown summary designed to be pasted back for review."""
    r = manifest["results"]
    rs = manifest["parameters"].get("river_source", "hydrorivers")
    lines = [f"# NOWRI run summary - mode `{manifest['mode']}` - river source `{rs}`", "",
             f"- Run: `{manifest['run_id']}`  |  pipeline {manifest['pipeline_version']}  |  commit `{manifest['git_commit']}`",
             f"- Extraction box (lon/lat): `{manifest['parameters']['extraction_bbox_lon_lat']}`",
             f"- Total records: **{r['total_records']}**  |  assigned to pilot states: **{r['assigned_total']}**  |  "
             f"unassigned: **{r['unassigned_total']}**",
             f"- Direct intersections: **{r['intersections_total']}**  |  unique OGIM IDs: {r['unique_ogim_ids_total']}",
             f"- Consistency-audit problems: **{manifest['quality_control']['consistency_audit_problems']}**", ""]
    lines += ["## Bands (assigned records)", ""]
    for band, n in r["bands_assigned"].items():
        lines.append(f"- {band}: {n}")
    lines += ["", "## Records by layer (total / assigned / intersecting)", ""]
    for name, n in r["records_by_layer"].items():
        lines.append(f"- {name}: {n} / {r['assigned_by_layer'][name]} / {r['intersections_by_layer'][name]}")
    lines += ["", "## Records by state (assigned)", ""]
    for st, n in r["records_by_state"].items():
        lines.append(f"- {st}: {n}")
    if manifest.get("extra_layers_included"):
        lines += ["", f"## Extra layers included: {', '.join(manifest['extra_layers_included'])}"]
    if checks is not None:
        bad = [c for c in checks if not c["ok"]]
        n_ok = len(checks) - len(bad)
        if manifest["mode"] == "legacy":
            lines += ["", f"## Regression vs documented v0.1 baseline: "
                          f"{'PASS' if not bad else 'FAIL'} ({n_ok}/{len(checks)} checks passed)"]
            for c in bad:
                lines.append(f"- MISMATCH {c['check']}: expected {c['expected']}, observed {c['observed']}")
        else:
            lines += ["", "## Change relative to the documented v0.1 baseline (informational)", "",
                      "The extraction extent differs from v0.1 on purpose, so differences are expected "
                      f"(this is not a test). {n_ok} of {len(checks)} baseline values are unchanged.", "",
                      "| quantity | v0.1 | now | change |", "|---|---:|---:|---:|"]
            for c in bad:
                e, o = c["expected"], c["observed"]
                diff = f"{o - e:+d}" if isinstance(e, int) and isinstance(o, int) else ""
                lines.append(f"| {c['check']} | {e} | {o} | {diff} |")
    if record_level is not None:
        lines += ["", f"## Record-level regression vs v0.1 GeoPackage: {'PASS' if record_level['passed'] else 'FAIL'}",
                  f"- only in new: {record_level['only_in_new']}; only in baseline: {record_level['only_in_base']}",
                  f"- intersection-flag mismatches: {record_level['intersection_flag_mismatches']}",
                  f"- band mismatches: {record_level['band_mismatches']} "
                  f"(explained by rounding at a band edge: {record_level['band_mismatches_explained_by_rounding']}, "
                  f"unexplained: {record_level['band_mismatches_unexplained']})"]
    pc = manifest.get("projection_check")
    if pc and "error" not in pc:
        lines += ["", f"## Projection sensitivity (sample of {pc['sample_size']} records, up to 10 per layer)", "",
                  f"- tied nearest-river records: {pc['tied_nearest_river_records']}; zero-distance records: "
                  f"{pc['zero_distance_records']}; non-zero comparisons: {pc['nonzero_distance_records']}",
                  f"- mean / median / 75th percentile / maximum absolute difference (m): "
                  f"{pc['mean_absolute_difference_m']:.6f} / {pc['median_absolute_difference_m']:.6f} / "
                  f"{pc['p75_absolute_difference_m']:.6f} / {pc['maximum_absolute_difference_m']:.6f}",
                  f"- mean / maximum percentage difference: {pc['mean_difference_percent']:.6f}% / "
                  f"{pc['maximum_difference_percent']:.6f}%",
                  f"- stored distances matching the recalculation: {pc['stored_distances_matching']} of {pc['sample_size']}",
                  "- statistics are over the non-zero-distance records only (as in the v0.1 verification)"]
    elif pc:
        lines += ["", f"## Projection sensitivity: NOT COMPUTED ({pc['error']})"]
    if tolerance is not None and len(tolerance):
        lines += ["", "## Tolerance sensitivity (assigned records: intersecting or within t metres)", "",
                  "| t (m) | records | % |", "|---:|---:|---:|"]
        for _, row in tolerance.iterrows():
            lines.append(f"| {row['tolerance_m']:.0f} | {int(row['records_intersecting_or_within'])} | {row['percent_of_records']} |")
    if coverage is not None and len(coverage):
        lines += ["", "## OGIM layer coverage audit (Nigerian records inside extraction box)", ""]
        for _, row in coverage.iterrows():
            lines.append(f"- {row['ogim_layer']}: {row['nigerian_records_in_box']}"
                         + (f"  (error: {row['error']})" if isinstance(row.get('error'), str) and row['error'] else ""))
    lines += ["", "## Sources", ""]
    for s in manifest["sources"]:
        lines.append(f"- {s.get('name')} {s.get('version', '')}: licence = {s.get('licence_recorded')}")
    lines.append("")
    return "\n".join(lines)
