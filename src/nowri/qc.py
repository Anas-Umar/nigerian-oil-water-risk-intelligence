"""Quality control, summaries and regression checks (pure pandas/numpy/sqlite3).

These functions never touch geometry, so they are unit-testable without
GeoPandas. The geometry work happens in ``pipeline.py``.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np
import pandas as pd

from .config import (
    BAND_EDGES_M,
    BAND_LABELS,
    BASELINE_V01,
    CORE_LAYER_NAMES,
    PILOT_STATES,
)
from .proximity import band_counts, classify_bands

PLACEHOLDER_DATE_PREFIX = "1900-01-01"
_NONE_SENTINEL = "<none>"


# ---------------------------------------------------------------------------
# Placeholders / missingness
# ---------------------------------------------------------------------------
def placeholder_counts(df: pd.DataFrame, exclude: Iterable[str] = ("geometry",)) -> Dict[str, int]:
    """Count literal 'N/A' strings, -999 sentinels, 1900-01-01 dates and nulls."""
    na = m999 = d1900 = nulls = 0
    for col in df.columns:
        if col in set(exclude):
            continue
        s = df[col]
        nulls += int(s.isna().sum())
        if pd.api.types.is_numeric_dtype(s):
            m999 += int((s == -999).sum())
        else:
            ss = s.dropna().astype(str).str.strip()
            na += int((ss.str.upper() == "N/A").sum())
            d1900 += int(ss.str.startswith(PLACEHOLDER_DATE_PREFIX).sum())
    return {
        "literal_NA_occurrences": na,
        "numeric_minus_999_sentinels": m999,
        "placeholder_dates_1900_01_01": d1900,
        "actual_null_cells": nulls,
    }


# ---------------------------------------------------------------------------
# Internal-consistency audit of stored flags / distances / bands
# ---------------------------------------------------------------------------
def audit_table(df: pd.DataFrame, layer: str = "") -> List[dict]:
    """Return a list of problems (empty list == clean).

    Required columns: OGIM_ID, SPATIAL_STATE, Intersects_mapped_river,
    Distance_to_river_m, Distance_band, Distance_band_to_pilot_network.
    """
    problems: List[dict] = []
    inter = df["Intersects_mapped_river"].astype(bool).to_numpy()
    d = df["Distance_to_river_m"].astype(float).to_numpy()
    ids = df["OGIM_ID"].astype(str).to_numpy()
    assigned = df["SPATIAL_STATE"].notna().to_numpy()

    def add(mask, text):
        for i in np.flatnonzero(mask):
            problems.append({"layer": layer, "OGIM_ID": ids[i], "problem": text,
                             "distance_m": None if np.isnan(d[i]) else float(d[i])})

    add(np.isnan(d), "null distance")
    add(inter & ~np.isnan(d) & (d != 0), "flag=True but distance != 0")
    add(~inter & (d == 0), "flag=False but distance == 0")

    expected = pd.Series(classify_bands(inter, d), dtype="object").fillna(_NONE_SENTINEL).to_numpy()
    pilot = df["Distance_band_to_pilot_network"].astype(object).where(
        df["Distance_band_to_pilot_network"].notna(), _NONE_SENTINEL).to_numpy()
    add(pilot != expected, "Distance_band_to_pilot_network != recomputed band")

    band = df["Distance_band"].astype(object).where(df["Distance_band"].notna(), _NONE_SENTINEL).to_numpy()
    add(assigned & (band != expected), "Distance_band != recomputed band (assigned record)")
    add(~assigned & (band != _NONE_SENTINEL), "Distance_band set for unassigned record")
    return problems


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------
def summarise(tables: Mapping[str, pd.DataFrame], layer_names: Optional[Iterable[str]] = None) -> dict:
    """Aggregate counts used in reports and in the baseline regression."""
    names = list(layer_names) if layer_names is not None else list(tables)
    records, assigned_n, inter_n, uniq = {}, {}, {}, {}
    bands_by_layer: Dict[str, dict] = {}
    all_assigned_bands: List = []
    state_bands: Dict[str, List] = {s: [] for s in PILOT_STATES}
    state_counts = {s: 0 for s in PILOT_STATES}
    all_ids: List[str] = []

    for name in names:
        df = tables.get(name)
        if df is None:
            continue
        a = df["SPATIAL_STATE"].notna()
        records[name] = int(len(df))
        assigned_n[name] = int(a.sum())
        inter_n[name] = int(df["Intersects_mapped_river"].astype(bool).sum())
        ids = df["OGIM_ID"].astype(str)
        uniq[name] = int(ids.nunique())
        all_ids.extend(ids.tolist())
        bands_by_layer[name] = band_counts(df.loc[a, "Distance_band"])
        all_assigned_bands.extend(df.loc[a, "Distance_band"].tolist())
        for st in PILOT_STATES:
            m = a & (df["SPATIAL_STATE"] == st)
            state_counts[st] += int(m.sum())
            state_bands[st].extend(df.loc[m, "Distance_band"].tolist())

    total = int(sum(records.values()))
    assigned_total = int(sum(assigned_n.values()))
    return {
        "records_by_layer": records,
        "assigned_by_layer": assigned_n,
        "intersections_by_layer": inter_n,
        "unique_ogim_ids_by_layer": uniq,
        "total_records": total,
        "assigned_total": assigned_total,
        "unassigned_total": total - assigned_total,
        "intersections_total": int(sum(inter_n.values())),
        "unique_ogim_ids_total": int(len(set(all_ids))),
        "bands_assigned": band_counts(all_assigned_bands),
        "bands_assigned_by_layer": bands_by_layer,
        "bands_assigned_by_state": {s: band_counts(v) for s, v in state_bands.items()},
        "records_by_state": state_counts,
    }


# ---------------------------------------------------------------------------
# Regression against the documented v0.1 baseline
# ---------------------------------------------------------------------------
def compare_to_baseline(summary: dict, river_info: Optional[dict] = None,
                        baseline: Optional[dict] = None) -> List[dict]:
    """Check a summary against the v0.1 baseline. Each check: name/expected/observed/ok."""
    base = baseline or BASELINE_V01
    checks: List[dict] = []

    def chk(name, expected, observed):
        checks.append({"check": name, "expected": expected, "observed": observed,
                       "ok": expected == observed})

    for key in ("records_by_layer", "assigned_by_layer", "intersections_by_layer"):
        for layer, exp in base[key].items():
            chk(f"{key}.{layer}", exp, summary.get(key, {}).get(layer))
    for key in ("total_records", "assigned_total", "unassigned_total",
                "intersections_total", "unique_ogim_ids_total"):
        chk(key, base[key], summary.get(key))
    for band in BAND_LABELS:
        chk(f"bands_assigned.{band}", base["bands_assigned"][band],
            summary.get("bands_assigned", {}).get(band))
    for st, exp in base["records_by_state"].items():
        chk(f"records_by_state.{st}", exp, summary.get("records_by_state", {}).get(st))
    if river_info is not None:
        chk("river_sections_clipped", base["river_sections_clipped"],
            river_info.get("sections_clipped"))
        chk("river_unique_ids_clipped", base["river_unique_ids_clipped"],
            river_info.get("unique_ids_clipped"))
    return checks


def checks_passed(checks: List[dict]) -> bool:
    return all(c["ok"] for c in checks)


# ---------------------------------------------------------------------------
# Record-level comparison with a released v0.1 GeoPackage (read with sqlite3)
# ---------------------------------------------------------------------------
def read_baseline_gpkg(path: str, layers: Iterable[str] = CORE_LAYER_NAMES) -> pd.DataFrame:
    """Read the attributes needed for record-level regression from a v0.1 GeoPackage."""
    wanted = ["OGIM_ID", "SPATIAL_STATE", "Intersects_mapped_river",
              "Distance_to_river_km", "Distance_band", "Distance_band_to_pilot_network"]
    frames = []
    con = sqlite3.connect(path)
    try:
        for layer in layers:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{layer}")')]
            if not cols:
                continue
            use = [c for c in wanted if c in cols]
            df = pd.read_sql_query(f'SELECT {", ".join(chr(34)+c+chr(34) for c in use)} FROM "{layer}"', con)
            for c in wanted:          # e.g. the v0.1 'wells' layer has no SPATIAL_STATE column
                if c not in df.columns:
                    df[c] = None
            df.insert(0, "layer", layer)
            frames.append(df)
    finally:
        con.close()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _key_frame(df: pd.DataFrame, layer_col: Optional[str] = None) -> pd.DataFrame:
    out = df.copy()
    out["OGIM_ID"] = out["OGIM_ID"].astype(str)
    out["SPATIAL_STATE"] = out["SPATIAL_STATE"].where(out["SPATIAL_STATE"].notna(), "")
    lc = layer_col or "layer"
    out["key"] = out[lc].astype(str) + "|" + out["OGIM_ID"] + "|" + out["SPATIAL_STATE"].astype(str)
    return out


def compare_records(new_tables: Mapping[str, pd.DataFrame], base: pd.DataFrame,
                    edge_tolerance_m: float = 0.5, max_listed: int = 50) -> dict:
    """Record-level comparison of new results with the v0.1 baseline.

    Band differences are 'explained' only if the unrounded distance lies within
    ``edge_tolerance_m`` of a band edge (v0.1 classified on rounded kilometres).
    """
    frames = []
    for layer in CORE_LAYER_NAMES:
        df = new_tables.get(layer)
        if df is None:
            continue
        part = df[["OGIM_ID", "SPATIAL_STATE", "Intersects_mapped_river",
                   "Distance_to_river_m", "Distance_band_to_pilot_network"]].copy()
        part.insert(0, "layer", layer)
        frames.append(part)
    new = _key_frame(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
    b = _key_frame(base)

    dup_new = int(new["key"].duplicated().sum()) if len(new) else 0
    dup_base = int(b["key"].duplicated().sum()) if len(b) else 0
    merged = new.merge(b, on="key", how="outer", suffixes=("_new", "_base"), indicator=True)
    only_new = merged[merged["_merge"] == "left_only"]
    only_base = merged[merged["_merge"] == "right_only"]
    both = merged[merged["_merge"] == "both"].copy()

    flag_mismatch = both[both["Intersects_mapped_river_new"].astype(bool)
                         != both["Intersects_mapped_river_base"].astype(bool)]
    bn = both["Distance_band_to_pilot_network_new"].astype(object).where(
        both["Distance_band_to_pilot_network_new"].notna(), _NONE_SENTINEL)
    bb = both["Distance_band_to_pilot_network_base"].astype(object).where(
        both["Distance_band_to_pilot_network_base"].notna(), _NONE_SENTINEL)
    band_mm = both[bn != bb].copy()
    if len(band_mm):
        dist = band_mm["Distance_to_river_m"].astype(float)
        near_edge = np.zeros(len(band_mm), dtype=bool)
        for edge in BAND_EDGES_M:
            near_edge |= (dist - edge).abs().to_numpy() <= edge_tolerance_m
        near_edge |= (dist <= edge_tolerance_m).to_numpy()   # 0-edge (tiny distances)
        band_mm["explained_by_rounding"] = near_edge
    unexplained = band_mm[~band_mm["explained_by_rounding"]] if len(band_mm) else band_mm

    def listing(df, cols):
        return df[cols].head(max_listed).to_dict("records") if len(df) else []

    return {
        "n_new": int(len(new)), "n_base": int(len(b)),
        "duplicate_keys_new": dup_new, "duplicate_keys_base": dup_base,
        "only_in_new": int(len(only_new)), "only_in_base": int(len(only_base)),
        "intersection_flag_mismatches": int(len(flag_mismatch)),
        "band_mismatches": int(len(band_mm)),
        "band_mismatches_explained_by_rounding": int(len(band_mm) - len(unexplained)),
        "band_mismatches_unexplained": int(len(unexplained)),
        "examples_only_in_new": listing(only_new, ["key"]),
        "examples_only_in_base": listing(only_base, ["key"]),
        "examples_flag_mismatch": listing(flag_mismatch, ["key", "Intersects_mapped_river_new",
                                                          "Intersects_mapped_river_base"]),
        "examples_band_unexplained": listing(unexplained, ["key", "Distance_to_river_m",
                                                           "Distance_band_to_pilot_network_new",
                                                           "Distance_band_to_pilot_network_base"]),
        "passed": bool(len(only_new) == 0 and len(only_base) == 0
                       and len(flag_mismatch) == 0 and len(unexplained) == 0
                       and dup_new == 0),
    }


# ---------------------------------------------------------------------------
# Sensitivity of results to the river-network clipping choice
# ---------------------------------------------------------------------------
def network_sensitivity(tables: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Compare results using the state-clipped vs unclipped river network.

    v0.1 (and the default here) measures distance to a river network clipped to
    the state polygons. That can create artificial edge effects, so the same
    quantities are recomputed against the unclipped network for assigned records.
    """
    rows = []
    for name, df in tables.items():
        need = {"Distance_to_unclipped_network_m", "Intersects_unclipped_network"}
        if not need.issubset(df.columns):
            continue
        a = df["SPATIAL_STATE"].notna()
        sub = df[a]
        full_bands = pd.Series(
            classify_bands(sub["Intersects_unclipped_network"].astype(bool),
                           sub["Distance_to_unclipped_network_m"].astype(float)),
            index=sub.index, dtype="object")
        clipped_bands = sub["Distance_band"].astype(object)
        changed = int((full_bands.fillna(_NONE_SENTINEL) != clipped_bands.fillna(_NONE_SENTINEL)).sum())
        rows.append({
            "layer": name,
            "assigned_records": int(len(sub)),
            "intersecting_clipped_network": int(sub["Intersects_mapped_river"].astype(bool).sum()),
            "intersecting_unclipped_network": int(sub["Intersects_unclipped_network"].astype(bool).sum()),
            "band_changed_vs_clipped": changed,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Projection-sensitivity statistics (pure; the geometry work is in projection_check.py)
# ---------------------------------------------------------------------------
ZERO_DISTANCE_M = 1e-6          # geodesic distances at or below this count as "zero" (v0.1 used 1e-9 km)


def summarise_projection_check(details: pd.DataFrame) -> dict:
    """Summary statistics, matching the v0.1 verification.

    ``details`` needs: layer, n_tied_matches, projected_distance_m, geodesic_distance_m,
    difference_m, difference_percent, stored_matches. As in v0.1, the difference statistics are
    computed over the NON-ZERO records only (a percentage difference is undefined at zero distance).
    """
    nz = details[details["geodesic_distance_m"] > ZERO_DISTANCE_M]
    diff, pct = nz["difference_m"], nz["difference_percent"]

    def f(series, fn):
        return float(fn(series)) if len(series) else float("nan")

    return {
        "sample_size": int(len(details)),
        "layers_represented": int(details["layer"].nunique()),
        "tied_nearest_river_records": int((details["n_tied_matches"] > 1).sum()),
        "zero_distance_records": int((details["geodesic_distance_m"] <= ZERO_DISTANCE_M).sum()),
        "nonzero_distance_records": int(len(nz)),
        "mean_absolute_difference_m": f(diff, np.mean),
        "median_absolute_difference_m": f(diff, np.median),
        "p75_absolute_difference_m": f(diff, lambda s: np.quantile(s, 0.75)),
        "maximum_absolute_difference_m": f(diff, np.max),
        "mean_difference_percent": f(pct, np.mean),
        "maximum_difference_percent": f(pct, np.max),
        "stored_distances_matching": int(details["stored_matches"].sum()),
        "stored_distances_mismatching": int((~details["stored_matches"].astype(bool)).sum()),
        "statistics_population": "non-zero-distance records only (as in the v0.1 verification)",
    }
