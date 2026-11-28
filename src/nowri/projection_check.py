"""Projection-sensitivity check (replicates the v0.1 verification, now part of every run).

For a reproducible sample of up to ``n_per_layer`` records per layer, the nearest river reach is
found in the AEQD projection (ties kept), the nearest-point pair is transformed back to geographic
coordinates and the WGS 84 ellipsoidal distance between the pair is compared with the projected
distance. Among tied reaches the smallest ellipsoidal distance is kept. The check asks how much the
projection distorts the distances for these pairs; it does not prove the projected pair is the
globally nearest pair under ellipsoidal distance.
"""
from __future__ import annotations

from typing import Dict, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod, Transformer
from shapely.ops import nearest_points

from . import config as C
from . import qc

SAMPLE_PER_LAYER = 10
SEED = 42


def projection_check(tables: Dict[str, gpd.GeoDataFrame], rivers_m: gpd.GeoDataFrame,
                     n_per_layer: int = SAMPLE_PER_LAYER, seed: int = SEED) -> Tuple[pd.DataFrame, dict]:
    """``tables``: layer GeoDataFrames in EPSG:4326 (unique index). ``rivers_m``: river network in the analysis CRS."""
    to_wgs = Transformer.from_crs(C.ANALYSIS_CRS, "EPSG:4326", always_xy=True)
    geod = Geod(ellps="WGS84")
    rivers = rivers_m[["geometry"]].reset_index(drop=True)
    rows = []
    for name in C.CORE_LAYER_NAMES:
        g = tables.get(name)
        if g is None or len(g) == 0:
            continue
        sample = g.sample(n=min(n_per_layer, len(g)), random_state=seed)
        am = sample[["OGIM_ID", "geometry"]].to_crs(C.ANALYSIS_CRS)
        joined = gpd.sjoin_nearest(am, rivers, how="left", distance_col="projected_m")
        for idx, grp in joined.groupby(level=0):
            asset = am.loc[idx, "geometry"]
            candidates = []
            for _, r in grp.iterrows():
                river_geom = rivers.loc[int(r["index_right"]), "geometry"]
                p_asset, p_river = nearest_points(asset, river_geom)
                lon_a, lat_a = to_wgs.transform(p_asset.x, p_asset.y)
                lon_r, lat_r = to_wgs.transform(p_river.x, p_river.y)
                _, _, d = geod.inv(lon_a, lat_a, lon_r, lat_r)
                candidates.append((abs(float(d)), float(r["projected_m"])))
            geodesic_m, projected_m = min(candidates)
            diff = abs(projected_m - geodesic_m)
            stored = float(g.loc[idx, "Distance_to_river_m"])
            rows.append({
                "layer": name, "OGIM_ID": str(am.loc[idx, "OGIM_ID"]), "n_tied_matches": int(len(grp)),
                "projected_distance_m": projected_m, "geodesic_distance_m": geodesic_m,
                "difference_m": diff,
                "difference_percent": (100.0 * diff / geodesic_m) if geodesic_m > qc.ZERO_DISTANCE_M else np.nan,
                "stored_distance_m": stored, "stored_matches": bool(abs(stored - projected_m) <= 1e-6),
            })
    details = pd.DataFrame(rows)
    return details, qc.summarise_projection_check(details)
