"""NOWRI geospatial pipeline (requires geopandas, shapely, pyproj, pyogrio).

Two modes
---------
``legacy``  Re-runs the v0.1 method with the original extraction box
            (4.5, 4.0, 7.0, 6.5). It must reproduce the documented v0.1 baseline;
            this proves the refactored code did not change the science.
``state``   Takes the extraction box from the state polygons plus a margin, which
            fixes the truncation of Rivers State at 7.0 E found in the v0.1 audit.

Method (identical in both modes)
--------------------------------
* Infrastructure from OGIM v3.0 inside the box, Nigerian records only.
* Lines and polygons are clipped to each pilot state (state-specific sections).
  Points are assigned with a 'within' spatial join; points outside the three
  polygons are kept and labelled as unassigned.
* Rivers: HydroRIVERS (Africa) inside the box, clipped to the state polygons.
* Distances: minimum planar distance in the custom AEQD projection to that
  network (unrounded metres). Intersection is a geometric test.
* Distance bands are computed from unrounded distances.
"""
from __future__ import annotations

import json
import logging
import os
import time
import datetime as dt
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely.geometry import box
from pyproj import Geod

from . import config as C
from . import proximity, qc, release, sources

log = logging.getLogger("nowri")
GEOD = Geod(ellps="WGS84")


# ---------------------------------------------------------------------------
# Small geometry helpers
# ---------------------------------------------------------------------------
def _force_2d(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop Z coordinates (OGIM pipelines/fields are 3-D)."""
    if len(gdf) == 0:
        return gdf
    out = gdf.copy()
    try:
        out["geometry"] = out.geometry.force_2d()
    except AttributeError:
        out["geometry"] = gpd.GeoSeries(
            [shapely.force_2d(g) for g in out.geometry], index=out.index, crs=out.crs)
    return out


def _geodesic_length(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    gt = geom.geom_type
    if gt in ("LineString", "MultiLineString", "LinearRing"):
        return float(GEOD.geometry_length(geom))
    if hasattr(geom, "geoms"):
        return float(sum(_geodesic_length(g) for g in geom.geoms))
    return 0.0


def _geodesic_area(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    gt = geom.geom_type
    if gt in ("Polygon", "MultiPolygon"):
        return abs(float(GEOD.geometry_area_perimeter(geom)[0]))
    if hasattr(geom, "geoms"):
        return float(sum(_geodesic_area(g) for g in geom.geoms))
    return 0.0


def _fix_invalid(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    if len(gdf) == 0:
        return gdf
    bad = ~gdf.geometry.is_valid
    n = int(bad.sum())
    if n:
        log.warning("%s: repairing %d invalid geometries with make_valid", label, n)
        gdf = gdf.copy()
        gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].make_valid()
    return gdf


# ---------------------------------------------------------------------------
# Study area
# ---------------------------------------------------------------------------
def load_states(path: str) -> gpd.GeoDataFrame:
    states = gpd.read_file(path)
    states = states[states["shapeName"].isin(C.PILOT_STATES)].copy()
    found = sorted(states["shapeName"].tolist())
    if found != sorted(C.PILOT_STATES):
        raise ValueError(f"Expected states {sorted(C.PILOT_STATES)}, found {found}")
    states = states[["shapeName", "geometry"]].to_crs(4326)
    states = _fix_invalid(states, "states").reset_index(drop=True)
    return states


def extraction_bbox(mode: str, states: gpd.GeoDataFrame, margin: float) -> Tuple[float, float, float, float]:
    if mode == "legacy":
        return tuple(C.LEGACY_BBOX)
    if mode != "state":
        raise ValueError("mode must be 'legacy' or 'state'")
    minx, miny, maxx, maxy = (float(v) for v in states.total_bounds)
    return (round(minx - margin, 4), round(miny - margin, 4),
            round(maxx + margin, 4), round(maxy + margin, 4))


# ---------------------------------------------------------------------------
# Reading and preparing infrastructure layers
# ---------------------------------------------------------------------------
def read_ogim_layer(gpkg: str, spec: C.LayerSpec, bbox) -> Tuple[gpd.GeoDataFrame, int]:
    gdf = gpd.read_file(gpkg, layer=spec.ogim_layer, bbox=tuple(bbox), engine="pyogrio")
    n_bbox = int(len(gdf))
    if n_bbox == 0:
        return gdf, 0
    if "COUNTRY" in gdf.columns:
        gdf = gdf[gdf["COUNTRY"].astype(str).str.strip().str.upper() == "NIGERIA"]
    gdf = _force_2d(gdf.copy())
    if len(gdf):
        gdf["OGIM_ID"] = gdf["OGIM_ID"].astype(str)
    return gdf.reset_index(drop=True), n_bbox


def _clip_by_state(g: gpd.GeoDataFrame, states: gpd.GeoDataFrame, kind: str,
                   strict: bool) -> Tuple[gpd.GeoDataFrame, int]:
    parts = []
    for name in states["shapeName"]:
        mask = states[states["shapeName"] == name]
        c = gpd.clip(g, mask, keep_geom_type=strict)
        c = c[c.geometry.notna() & ~c.geometry.is_empty].copy()
        c["SPATIAL_STATE"] = name
        if kind == "line":
            c["CLIPPED_LENGTH_KM"] = [_geodesic_length(x) / 1000.0 for x in c.geometry]
        else:
            c["CLIPPED_AREA_KM2"] = [_geodesic_area(x) / 1e6 for x in c.geometry]
        parts.append(c)
    out = pd.concat(parts, ignore_index=True) if parts else g.iloc[0:0].copy()
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=g.crs)
    dropped = 0
    if strict and len(out):
        col = "CLIPPED_LENGTH_KM" if kind == "line" else "CLIPPED_AREA_KM2"
        keep = out[col] > 0
        dropped = int((~keep).sum())
        out = out[keep].copy()
    out = out.reset_index(drop=True)
    out["Section_ID"] = out.index.astype(str)
    return out, dropped


def prepare_lines(gdf, states, bbox, strict):
    g = gdf.copy()
    g["geometry"] = g.geometry.intersection(box(*bbox))
    g = g[(~g.geometry.is_empty)
          & g.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    return _clip_by_state(g, states, "line", strict)


def prepare_polygons(gdf, states, strict):
    return _clip_by_state(_fix_invalid(gdf, "polygons"), states, "polygon", strict)


def assign_points(gdf: gpd.GeoDataFrame, states: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, int]:
    j = gpd.sjoin(gdf, states[["shapeName", "geometry"]], how="left", predicate="within")
    dup = j.index.duplicated(keep="first")
    n_dup = int(dup.sum())
    j = j[~dup].drop(columns=["index_right"], errors="ignore")
    j = j.rename(columns={"shapeName": "SPATIAL_STATE"})
    return j, n_dup


# ---------------------------------------------------------------------------
# Rivers
# ---------------------------------------------------------------------------
def load_rivers(shp, bbox, states: gpd.GeoDataFrame):
    """``shp`` is one shapefile path (HydroRIVERS) or a list of tile paths (RiverATLAS)."""
    if isinstance(shp, (list, tuple)) and len(shp) > 1:
        frames = [gpd.read_file(p, bbox=tuple(bbox)) for p in shp]
        rivers = gpd.GeoDataFrame(pd.concat([f[["HYRIV_ID", "geometry"]] for f in frames], ignore_index=True),
                                  geometry="geometry", crs=frames[0].crs)
        rivers = rivers.drop_duplicates(subset="HYRIV_ID").reset_index(drop=True)
    else:
        path = shp[0] if isinstance(shp, (list, tuple)) else shp
        rivers = gpd.read_file(path, bbox=tuple(bbox))
        rivers = rivers[["HYRIV_ID", "geometry"]].copy()
    clipped = gpd.overlay(rivers, states[["shapeName", "geometry"]],
                          how="intersection", keep_geom_type=True)
    clipped = clipped[~clipped.geometry.is_empty].copy()
    info = {"records_in_box": int(len(rivers)),
            "sections_clipped": int(len(clipped)),
            "unique_ids_clipped": int(clipped["HYRIV_ID"].nunique())}
    return rivers, clipped[["HYRIV_ID", "shapeName", "geometry"]], info


# ---------------------------------------------------------------------------
# Proximity
# ---------------------------------------------------------------------------
def compute_proximity(assets_m: gpd.GeoDataFrame, rivers_m: gpd.GeoDataFrame) -> pd.DataFrame:
    """Nearest-river distance (m), tied-match count and geometric intersection flag.

    ``assets_m`` and ``rivers_m`` must share a projected CRS in metres. The result
    is index-aligned with ``assets_m`` (which must have a unique index).
    """
    a = assets_m[["geometry"]].copy()
    r = rivers_m[["HYRIV_ID", "geometry"]].copy()
    nearest = gpd.sjoin_nearest(a, r, how="left", distance_col="dist_m")
    grp = nearest.groupby(level=0)
    dist = grp["dist_m"].min().reindex(a.index)
    matches = grp["HYRIV_ID"].nunique().reindex(a.index)
    hit = gpd.sjoin(a, r, how="inner", predicate="intersects")
    flag = a.index.isin(hit.index.unique())
    out = pd.DataFrame({"dist_m": dist.astype(float).to_numpy(),
                        "matches": matches.to_numpy(),
                        "intersects": np.asarray(flag, dtype=bool)}, index=a.index)
    out.loc[out["intersects"], "dist_m"] = 0.0
    return out


def state_attribute_conflict(source_state: pd.Series, spatial_state: pd.Series) -> np.ndarray:
    """True where OGIM's STATE_PROV disagrees with the spatially derived pilot state."""
    src = (source_state.astype(str).str.upper().str.strip()
           .str.replace(r"\s+STATE$", "", regex=True).str.strip())
    spatial = spatial_state.astype(str).str.upper().str.strip()
    usable = spatial_state.notna() & ~src.isin(["", "N/A", "NAN", "NONE"])
    return (usable & (src != spatial)).to_numpy(dtype=bool)


def build_layer_gdf(spec: C.LayerSpec, prepared: gpd.GeoDataFrame,
                    rivers_clipped_m: gpd.GeoDataFrame,
                    rivers_full_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = prepared.copy().reset_index(drop=True)
    g_m = g.to_crs(C.ANALYSIS_CRS)
    prox = compute_proximity(g_m, rivers_clipped_m)
    prox_full = compute_proximity(g_m, rivers_full_m)

    assigned = g["SPATIAL_STATE"].notna().to_numpy()
    d = prox["dist_m"].to_numpy(float)
    inter = prox["intersects"].to_numpy(bool)
    bands_all = proximity.classify_bands(inter, d)

    g["Asset_category"] = spec.asset_category
    g["Unit_type"] = spec.unit_type
    if spec.subtype_constant:
        g["Asset_subtype"] = spec.subtype_constant
    elif spec.subtype_column and spec.subtype_column in g.columns:
        sub = g[spec.subtype_column]
        g["Asset_subtype"] = sub.where(sub.notna(), "N/A").astype(str)
    else:
        g["Asset_subtype"] = "N/A"
    if spec.kind == "point" and "STATE_PROV" in g.columns:
        g["Source_state"] = g["STATE_PROV"]
        g["State_attribute_conflict"] = state_attribute_conflict(g["STATE_PROV"], g["SPATIAL_STATE"])

    g["Distance_to_river_m"] = d
    g["Distance_to_river_km"] = proximity.round_km(d)
    g["Nearest_river_matches"] = pd.Series(prox["matches"].to_numpy()).fillna(0).astype("int64").to_numpy()
    g["Intersects_mapped_river"] = inter
    g["Distance_band"] = pd.Series(np.where(assigned, bands_all, None), index=g.index, dtype="object")
    g["Location_assignment"] = np.where(assigned, C.LOC_ASSIGNED, C.LOC_UNASSIGNED)
    g["Distance_band_to_pilot_network"] = pd.Series(bands_all, index=g.index, dtype="object")
    g["Distance_to_unclipped_network_m"] = prox_full["dist_m"].to_numpy(float)
    g["Intersects_unclipped_network"] = prox_full["intersects"].to_numpy(bool)
    return g


def process_layer(spec: C.LayerSpec, ogim_path: str, bbox, states, rivers_clipped_m,
                  rivers_full_m, strict: bool) -> Optional[gpd.GeoDataFrame]:
    t0 = time.time()
    gdf, n_bbox = read_ogim_layer(ogim_path, spec, bbox)
    log.info("[%s] %s: %d features in box, %d Nigerian", spec.name, spec.ogim_layer, n_bbox, len(gdf))
    if len(gdf) == 0:
        return None
    gdf = _fix_invalid(gdf, spec.name)
    if spec.kind == "line":
        prepared, dropped = prepare_lines(gdf, states, bbox, strict)
        log.info("[%s] %d state-specific sections (%d degenerate dropped)", spec.name, len(prepared), dropped)
    elif spec.kind == "polygon":
        prepared, dropped = prepare_polygons(gdf, states, strict)
        log.info("[%s] %d state-specific sections (%d degenerate dropped)", spec.name, len(prepared), dropped)
    else:
        prepared, n_dup = assign_points(gdf, states)
        log.info("[%s] %d points; %d assigned to a pilot state; %d duplicate join rows removed",
                 spec.name, len(prepared), int(prepared["SPATIAL_STATE"].notna().sum()), n_dup)
    if len(prepared) == 0:
        return None
    out = build_layer_gdf(spec, prepared, rivers_clipped_m, rivers_full_m)
    log.info("[%s] done in %.1f s", spec.name, time.time() - t0)
    return out


# ---------------------------------------------------------------------------
# Coverage audit of all OGIM layers
# ---------------------------------------------------------------------------
def coverage_audit(ogim_path: str, bbox_new, bbox_legacy) -> pd.DataFrame:
    import pyogrio
    rows = []
    for layer in [str(x[0]) for x in pyogrio.list_layers(ogim_path)]:
        if layer == "Data_Catalog":
            continue
        row = {"ogim_layer": layer, "error": ""}
        for tag, bb in (("nigerian_records_in_box", bbox_new),
                        ("nigerian_records_in_legacy_box", bbox_legacy)):
            try:
                try:
                    df = gpd.read_file(ogim_path, layer=layer, bbox=tuple(bb),
                                       engine="pyogrio", columns=["COUNTRY"])
                except Exception:  # layer without COUNTRY etc.
                    df = gpd.read_file(ogim_path, layer=layer, bbox=tuple(bb), engine="pyogrio")
                if "COUNTRY" in df.columns:
                    n = int((df["COUNTRY"].astype(str).str.strip().str.upper() == "NIGERIA").sum())
                else:
                    n = int(len(df))
                row[tag] = n
            except Exception as exc:  # noqa: BLE001
                row[tag] = None
                row["error"] = str(exc)[:160]
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _setup_logging(path: str) -> None:
    root = logging.getLogger("nowri")
    root.handlers.clear()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(), logging.FileHandler(path, encoding="utf-8")):
        h.setFormatter(fmt)
        root.addHandler(h)


def _plain(t: gpd.GeoDataFrame) -> pd.DataFrame:
    return pd.DataFrame(t.drop(columns="geometry"))


def run(mode: str, workdir: str, outdir: str, reports_dir: str,
        ogim_path: Optional[str] = None, baseline_gpkg: Optional[str] = None,
        margin: float = C.DEFAULT_MARGIN_DEG, skip_audit: bool = False,
        river_source: str = "riveratlas", riveratlas_zip: Optional[str] = None) -> dict:
    """Run the full pipeline. Returns a dict with 'passed' and output locations."""
    t_start = time.time()
    if river_source not in C.RIVER_SOURCES:
        raise ValueError(f"river_source must be one of {C.RIVER_SOURCES}")
    tag = mode if river_source == "hydrorivers" else f"{mode}_{river_source}"
    run_id = f"{tag}_{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
    run_dir = os.path.join(outdir, run_id)
    rep_dir = os.path.join(reports_dir, tag)
    for d in (workdir, run_dir, rep_dir):
        os.makedirs(d, exist_ok=True)
    _setup_logging(os.path.join(run_dir, "run.log"))
    versions = release.collect_versions()
    log.info("NOWRI pipeline %s | mode=%s | river source=%s | run_id=%s",
             C.PIPELINE_VERSION, mode, river_source, run_id)
    log.info("Software: %s", json.dumps(versions))

    # 1. Sources ------------------------------------------------------------
    s_ogim = sources.fetch_ogim(workdir, ogim_path)
    if river_source == "riveratlas":
        s_hydro = sources.fetch_riveratlas(workdir, riveratlas_zip)
        river_paths = s_hydro["paths"]
    else:
        s_hydro = sources.fetch_hydrorivers(workdir)
        river_paths = s_hydro["path"]
    s_bound = sources.fetch_boundaries(workdir)

    # 2. Study area -----------------------------------------------------------
    states = load_states(s_bound["path"])
    bbox = extraction_bbox(mode, states, margin)
    log.info("State polygon bounds (lon/lat): %s", [round(float(v), 4) for v in states.total_bounds])
    log.info("Extraction box (lon/lat): %s", bbox)
    if mode == "legacy":
        log.warning("LEGACY box in use: it stops at 7.0 E; state polygons extend to %.2f E.",
                    float(states.total_bounds[2]))

    # 3. Rivers ---------------------------------------------------------------
    rivers_full, rivers_clipped, river_info = load_rivers(river_paths, bbox, states)
    log.info("Rivers: %s", river_info)
    rivers_full_m = rivers_full.to_crs(C.ANALYSIS_CRS)
    rivers_clipped_m = rivers_clipped.to_crs(C.ANALYSIS_CRS)

    # 4. Coverage audit ---------------------------------------------------------
    coverage = None
    if not skip_audit:
        log.info("Auditing coverage of all OGIM layers ...")
        coverage = coverage_audit(s_ogim["path"], bbox, C.LEGACY_BBOX)
        coverage.to_csv(os.path.join(run_dir, "layer_coverage_audit.csv"), index=False)
        log.info("\n%s", coverage.to_string(index=False))

    # 5. Layers -----------------------------------------------------------------
    strict = mode == "state"
    tables: Dict[str, gpd.GeoDataFrame] = {}
    for spec in C.CORE_LAYERS:
        t = process_layer(spec, s_ogim["path"], bbox, states, rivers_clipped_m, rivers_full_m, strict)
        if t is None:
            log.warning("Core layer %s is empty.", spec.name)
        else:
            tables[spec.name] = t
    extras: List[str] = []
    if mode == "state":
        for spec in C.EXTRA_LAYERS:
            t = process_layer(spec, s_ogim["path"], bbox, states, rivers_clipped_m, rivers_full_m, strict)
            if t is not None:
                tables[spec.name] = t
                extras.append(spec.name)
                log.warning("Extra layer %s has %d records in the corrected extent.", spec.name, len(t))

    plain = {k: _plain(v) for k, v in tables.items()}

    # 6. QC ---------------------------------------------------------------------
    problems: List[dict] = []
    for name, df in plain.items():
        problems += qc.audit_table(df, name)
    if problems:
        log.error("Consistency audit found %d problem(s); first 5: %s", len(problems), problems[:5])
    summary = qc.summarise(plain, [n for n in C.CORE_LAYER_NAMES if n in plain])
    extras_summary = qc.summarise(plain, extras) if extras else None
    checks = qc.compare_to_baseline(summary, river_info)
    record_level = None
    if baseline_gpkg:
        record_level = qc.compare_records(plain, qc.read_baseline_gpkg(baseline_gpkg))
    ph = {"literal_NA_occurrences": 0, "numeric_minus_999_sentinels": 0,
          "placeholder_dates_1900_01_01": 0, "actual_null_cells": 0}
    for df in plain.values():
        for k, v in qc.placeholder_counts(df).items():
            ph[k] += v
    assigned_core = pd.concat([plain[n][plain[n]["SPATIAL_STATE"].notna()]
                               for n in C.CORE_LAYER_NAMES if n in plain], ignore_index=True)
    tol = proximity.tolerance_table(assigned_core["Intersects_mapped_river"].astype(bool),
                                    assigned_core["Distance_to_river_m"].astype(float))
    net = qc.network_sensitivity({n: plain[n] for n in C.CORE_LAYER_NAMES if n in plain})

    # 6b. Projection-sensitivity check (replicates the v0.1 verification). It must never stop a run.
    proj_summary = None
    try:
        from . import projection_check
        pdetails, proj_summary = projection_check.projection_check(tables, rivers_clipped_m)
        pdetails.to_csv(os.path.join(run_dir, "projection_check_details.csv"), index=False)
        log.info("Projection check: %s", {k: (round(v, 6) if isinstance(v, float) else v)
                                           for k, v in proj_summary.items()})
    except Exception as exc:  # noqa: BLE001
        log.warning("Projection check failed (the run continues): %s", exc)
        proj_summary = {"error": str(exc)[:300]}

    # 7. Write outputs --------------------------------------------------------------
    gpkg_path = os.path.join(run_dir, f"nowri_proximity_{mode}.gpkg")
    if os.path.exists(gpkg_path):
        os.remove(gpkg_path)
    for name, t in tables.items():
        t.to_file(gpkg_path, layer=name, driver="GPKG", engine="pyogrio")
    dd = release.build_data_dictionary(plain)
    dd_path = os.path.join(run_dir, "data_dictionary.csv")
    dd.to_csv(dd_path, index=False)
    tol.to_csv(os.path.join(run_dir, "tolerance_sensitivity.csv"), index=False)
    net.to_csv(os.path.join(run_dir, "network_sensitivity.csv"), index=False)

    outputs = [{"file": os.path.basename(p), "sha256": release.sha256_file(p),
                "size_bytes": os.path.getsize(p)} for p in (gpkg_path, dd_path)]
    manifest = release.build_manifest(
        run_id=run_id, mode=mode, bbox=bbox, margin_deg=margin, analysis_crs=C.ANALYSIS_CRS,
        sources=[sources.public_source_record(s) for s in (s_ogim, s_hydro, s_bound)],
        outputs=outputs,
        summary={**summary, "extras": extras_summary, "river_network": river_info},
        audit_problems=len(problems), regression=_checks_blob(checks, informational=(mode != "legacy")), record_level=record_level,
        extra_layers=extras, placeholders=ph, versions=versions, river_source=river_source,
        projection_check=proj_summary,
        commit=release.git_commit(os.path.dirname(os.path.abspath(__file__))))
    man_path = os.path.join(run_dir, "run_manifest.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    md = release.render_run_summary(manifest, checks, record_level, tol, coverage)
    with open(os.path.join(run_dir, "run_summary.md"), "w", encoding="utf-8") as f:
        f.write(md)

    # Figures for the paper (guarded: a plotting problem must not affect the analysis).
    fig_dir = os.path.join(rep_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    try:
        from . import figures
        figures.fig_bands_by_category(summary, os.path.join(fig_dir, "figure_4_2_bands_by_category.png"))
        figures.fig_bands_by_state(summary, os.path.join(fig_dir, "figure_4_3_bands_by_state.png"))
    except Exception as exc:  # noqa: BLE001
        log.warning("Bar-chart figures failed (the run continues): %s", exc)
    try:
        from . import figures
        figures.fig_study_area_map(states, rivers_clipped, tables,
                                   os.path.join(fig_dir, "figure_4_1_study_area_map.png"))
    except Exception as exc:  # noqa: BLE001
        log.warning("Study-area map failed (the run continues): %s", exc)

    # Small aggregate reports (no third-party records) for version control.
    for fname in ("run_summary.md", "run_manifest.json", "tolerance_sensitivity.csv",
                  "network_sensitivity.csv", "layer_coverage_audit.csv"):
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            with open(src, "rb") as fi, open(os.path.join(rep_dir, fname), "wb") as fo:
                fo.write(fi.read())
    # The full data dictionary quotes example values from OGIM, so only a copy without
    # examples goes into the committable reports folder.
    dd.drop(columns=["Example_values"]).to_csv(
        os.path.join(rep_dir, "data_dictionary_no_examples.csv"), index=False)

    regression_ok = qc.checks_passed(checks) and (record_level is None or record_level["passed"])
    passed = (len(problems) == 0) and (regression_ok if mode == "legacy" else True)
    log.info("=" * 70)
    reg_txt = ("PASS" if regression_ok else "FAIL") if mode == "legacy" else "n/a (informational in state mode)"
    log.info("RESULT (%s): consistency audit problems=%d | baseline regression=%s | passed=%s | %.0f s",
             mode, len(problems), reg_txt, passed, time.time() - t_start)
    log.info("Outputs: %s  |  committable reports: %s", run_dir, rep_dir)
    return {"passed": passed, "run_dir": run_dir, "reports_dir": rep_dir,
            "regression_ok": regression_ok, "audit_problems": len(problems)}


def _checks_blob(checks: List[dict], informational: bool = False) -> dict:
    bad = [c for c in checks if not c["ok"]]
    return {"informational": informational,
            "note": ("differences from v0.1 are expected: the extent was changed on purpose"
                     if informational else "regression test: all values must match the v0.1 baseline"),
            "passed": (not bad) if not informational else None,
            "n_checks": len(checks), "n_unchanged": len(checks) - len(bad),
            "n_changed": len(bad), "changed": bad}
