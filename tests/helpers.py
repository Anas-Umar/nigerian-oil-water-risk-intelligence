"""Synthetic tables shaped exactly like the documented v0.1 baseline."""
import numpy as np
import pandas as pd

import _path  # noqa: F401
from nowri import config as C

# per-layer band counts among ASSIGNED records (from the released v0.1 GeoPackage)
BANDS = {
    "pipelines":      (107, 4, 1, 0),
    "oil_gas_fields": (133, 15, 3, 1),
    "gas_processing": (0, 3, 2, 0),
    "offshore":       (0, 24, 12, 0),
    "terminals":      (0, 16, 6, 0),
    "refineries":     (0, 0, 1, 0),
    "stations":       (0, 149, 51, 0),
    "flaring":        (0, 192, 103, 0),
    "wells":          (0, 0, 0, 0),
}
UNIQUE = {"pipelines": 98, "oil_gas_fields": 142}  # other layers: all unique
DIST = {C.BAND_INTERSECT: 0.0, C.BAND_0_1: 500.0, C.BAND_1_5: 2000.0, C.BAND_GT5: 9000.0}


def make_baseline_tables():
    base = C.BASELINE_V01
    # states for the 823 assigned records, in the documented proportions
    states = (["Bayelsa"] * 185) + (["Rivers"] * 295) + (["Delta"] * 343)
    cursor = 0
    tables = {}
    for layer in C.CORE_LAYER_NAMES:
        n_total = base["records_by_layer"][layer]
        n_assigned = base["assigned_by_layer"][layer]
        counts = BANDS[layer]
        assert sum(counts) == n_assigned, layer
        bands, dists, flags = [], [], []
        for label, k in zip(C.BAND_LABELS, counts):
            bands += [label] * k
            dists += [DIST[label]] * k
            flags += [label == C.BAND_INTERSECT] * k
        n_un = n_total - n_assigned
        bands += [None] * n_un
        dists += [9000.0] * n_un
        flags += [False] * n_un
        st = states[cursor:cursor + n_assigned] + [None] * n_un
        cursor += n_assigned
        n_unique = UNIQUE.get(layer, n_total)
        ids = [f"{layer}-{i % n_unique}" for i in range(n_total)]
        pilot = [b if b is not None else C.BAND_GT5 for b in bands]
        tables[layer] = pd.DataFrame({
            "OGIM_ID": ids,
            "SPATIAL_STATE": st,
            "Intersects_mapped_river": flags,
            "Distance_to_river_m": dists,
            "Distance_band": bands,
            "Distance_band_to_pilot_network": pilot,
        })
    assert cursor == 823
    return tables
