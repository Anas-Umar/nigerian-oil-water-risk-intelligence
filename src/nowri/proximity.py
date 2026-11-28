"""Distance-band classification and tolerance sensitivity (pure pandas/numpy).

Design rules (these fix the root cause of the two-station error found in v0.1):

* The *intersection flag* comes from a geometric ``intersects`` test, never
  from a rounded distance.
* Bands are computed from the *unrounded* distance in metres.
* Rounded kilometres (3 d.p.) are kept only as a convenience field.

Bands are descriptive reporting categories, not risk thresholds.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .config import (
    BAND_0_1,
    BAND_1_5,
    BAND_EDGES_M,
    BAND_GT5,
    BAND_INTERSECT,
    BAND_LABELS,
    TOLERANCES_M,
)


def classify_bands(intersects: Iterable[bool], dist_m: Iterable[float]) -> np.ndarray:
    """Return an object array of band labels (``None`` where undefined).

    ``intersects`` takes precedence. Otherwise:
    0 < d <= 1000 m -> ">0-1 km"; 1000 < d <= 5000 m -> "1-5 km"; d > 5000 m -> ">5 km".
    """
    inter = np.asarray(list(intersects) if not hasattr(intersects, "__array__")
                       else intersects, dtype=bool)
    d = np.asarray(list(dist_m) if not hasattr(dist_m, "__array__") else dist_m,
                   dtype=float)
    if inter.shape != d.shape:
        raise ValueError("intersects and dist_m must have the same length")
    e1, e5 = BAND_EDGES_M
    out = np.select(
        [inter, d <= e1, d <= e5],
        [BAND_INTERSECT, BAND_0_1, BAND_1_5],
        default=BAND_GT5,
    ).astype(object)
    out[np.isnan(d) & ~inter] = None
    return out


def round_km(dist_m: Iterable[float], ndigits: int = 3) -> np.ndarray:
    """Metres -> kilometres rounded for display (never used to classify)."""
    return np.round(np.asarray(dist_m, dtype=float) / 1000.0, ndigits)


def tolerance_table(
    intersects: Sequence[bool],
    dist_m: Sequence[float],
    tolerances_m: Sequence[float] = TOLERANCES_M,
) -> pd.DataFrame:
    """How many records are 'intersecting or within t metres' for each t.

    Shows how sensitive the headline intersection count is to positional
    tolerance (HydroRIVERS is derived from 15 arc-second data).
    """
    inter = np.asarray(intersects, dtype=bool)
    d = np.asarray(dist_m, dtype=float)
    n = len(d)
    rows = []
    for t in tolerances_m:
        within = int(np.sum(inter | (d <= float(t))))
        rows.append({
            "tolerance_m": float(t),
            "records_intersecting_or_within": within,
            "percent_of_records": round(100.0 * within / n, 2) if n else float("nan"),
            "n_records": n,
        })
    return pd.DataFrame(rows)


def band_counts(bands: Iterable) -> dict:
    """Counts for the four labelled bands (zeros included), ignoring None."""
    s = pd.Series(list(bands), dtype="object").dropna()
    vc = s.value_counts()
    return {label: int(vc.get(label, 0)) for label in BAND_LABELS}
