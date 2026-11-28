"""Publication figures for the NOWRI results.

* ``fig_bands_by_category`` and ``fig_bands_by_state`` need only the summary numbers
  (pure matplotlib, unit-tested).
* ``fig_study_area_map`` needs the geometry (GeoPandas) and is therefore exercised in Colab / CI.

Colours are the Okabe-Ito colour-blind-safe palette. Every figure carries a data-source
line (the sources are CC BY 4.0 and require credit). Figures show distance to the nearest
*mapped* river reach: a screening quantity, not exposure or impact.
"""
from __future__ import annotations

from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")                      # no display needed (Colab, CI, servers)
import matplotlib.pyplot as plt  # noqa: E402

from .config import BAND_0_1, BAND_1_5, BAND_GT5, BAND_INTERSECT, BAND_LABELS  # noqa: E402

BAND_COLORS = {
    BAND_INTERSECT: "#D55E00",   # vermillion
    BAND_0_1: "#E69F00",         # orange
    BAND_1_5: "#009E73",         # bluish green
    BAND_GT5: "#0072B2",         # blue
}
CATEGORY_LABELS = {
    "pipelines": "Pipeline\nsections",
    "oil_gas_fields": "Oil and gas\nfields",
    "gas_processing": "Gas\nprocessing",
    "offshore": "Offshore\nplatforms",
    "terminals": "Terminals",
    "refineries": "Refineries",
    "stations": "Stations",
    "flaring": "Flaring\nsites",
    "wells": "Wells",
}
SOURCE_LINE = ("Data: OGIM v3.0 (CC BY 4.0); river network: RiverATLAS v1.0 / HydroRIVERS (CC BY 4.0); "
               "state boundaries: geoBoundaries (CC BY 4.0).")
BAND_ORDER = list(BAND_LABELS)


def _style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.linewidth": 0.8})


def fig_bands_by_category(summary: dict, path: str, dpi: int = 300) -> str:
    """Stacked bars: state-assigned records per infrastructure type, split by proximity category."""
    _style()
    data: Dict[str, Dict[str, int]] = summary["bands_assigned_by_layer"]
    layers = [k for k in CATEGORY_LABELS if k in data]
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    bottoms = [0] * len(layers)
    for band in BAND_ORDER:
        vals = [data[k].get(band, 0) for k in layers]
        ax.bar(range(len(layers)), vals, bottom=bottoms, color=BAND_COLORS[band], width=0.7,
               edgecolor="white", linewidth=0.5, label=band)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    for i, total in enumerate(bottoms):
        ax.text(i, total + max(bottoms) * 0.012, f"{total:,}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(layers)))
    ax.set_xticklabels([CATEGORY_LABELS[k] for k in layers], fontsize=7.3)
    ax.set_ylabel("State-assigned records")
    ax.set_ylim(0, max(bottoms) * 1.12)
    ax.legend(title="Distance to nearest mapped river", frameon=False, fontsize=8, title_fontsize=8,
              loc="upper left", bbox_to_anchor=(0.0, 1.0))
    fig.text(0.01, 0.005, SOURCE_LINE, fontsize=5.8, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def fig_bands_by_state(summary: dict, path: str, dpi: int = 300) -> str:
    """100 % stacked horizontal bars per state, annotated with percentages and record counts."""
    _style()
    data: Dict[str, Dict[str, int]] = summary["bands_assigned_by_state"]
    states = [s for s in ("Bayelsa", "Rivers", "Delta") if s in data]
    fig, ax = plt.subplots(figsize=(6.5, 2.9))
    for row, st in enumerate(reversed(states)):
        counts = [data[st].get(b, 0) for b in BAND_ORDER]
        total = sum(counts)
        left = 0.0
        for band, n in zip(BAND_ORDER, counts):
            share = 100.0 * n / total if total else 0.0
            ax.barh(row, share, left=left, color=BAND_COLORS[band], edgecolor="white", linewidth=0.5,
                    height=0.62, label=band if row == 0 else None)
            if share >= 6:
                ax.text(left + share / 2, row, f"{share:.1f}%", ha="center", va="center", fontsize=7.5,
                        color="white" if band in (BAND_INTERSECT, BAND_GT5, BAND_1_5) else "black")
            left += share
        ax.text(101.5, row, f"n = {total:,}", va="center", fontsize=8)
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels(list(reversed(states)))
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of state-assigned records (%)")
    ax.legend(title="Distance to nearest mapped river", frameon=False, fontsize=7.5, title_fontsize=7.5,
              ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.30), columnspacing=1.2, handlelength=1.2)
    fig.text(0.01, 0.005, SOURCE_LINE, fontsize=5.8, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 0.93, 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Study-area map (needs GeoPandas objects; exercised in Colab / CI)
# ---------------------------------------------------------------------------
MAP_STYLE = {
    "pipelines": dict(color="#444444", linewidth=0.7, label="Pipeline sections"),
    "oil_gas_fields": dict(color="#C9A66B", alpha=0.55, label="Oil and gas fields"),
    "flaring": dict(color="#E69F00", marker="^", markersize=5, label="Flaring sites"),
    "stations": dict(color="#CC79A7", marker="o", markersize=5, label="Stations"),
    "offshore": dict(color="black", marker="s", markersize=5, label="Offshore platforms"),
    "terminals": dict(color="#D55E00", marker="D", markersize=7, label="Terminals"),
    "refineries": dict(color="#D55E00", marker="*", markersize=16, label="Refineries"),
    "gas_processing": dict(color="#009E73", marker="P", markersize=8, label="Gas processing"),
}


def fig_study_area_map(states, rivers, tables: dict, path: str, dpi: int = 300) -> str:
    """Pilot states, mapped river network and state-assigned infrastructure by category.

    ``states`` and ``rivers`` are GeoDataFrames in EPSG:4326; ``tables`` maps layer name to a
    GeoDataFrame with a ``SPATIAL_STATE`` column (also EPSG:4326).
    """
    import math

    _style()
    fig, ax = plt.subplots(figsize=(6.5, 6.2))
    states.plot(ax=ax, color="#F2F2F2", edgecolor="#555555", linewidth=0.8)
    rivers.plot(ax=ax, color="#5B9BD5", linewidth=0.25, alpha=0.75)
    handles = []
    for name, style in MAP_STYLE.items():
        g = tables.get(name)
        if g is None or len(g) == 0:
            continue
        g = g[g["SPATIAL_STATE"].notna()]
        if len(g) == 0:
            continue
        kw = {k: v for k, v in style.items() if k != "label"}
        g.plot(ax=ax, zorder=3, **kw)
        kind = g.geom_type.iloc[0]
        if "Line" in kind:
            handles.append(plt.Line2D([0], [0], color=style["color"], linewidth=1.2, label=style["label"]))
        elif "Polygon" in kind:
            handles.append(plt.Rectangle((0, 0), 1, 1, color=style["color"], alpha=style.get("alpha", 1),
                                         label=style["label"]))
        else:
            handles.append(plt.Line2D([0], [0], marker=style["marker"], color="w", markerfacecolor=style["color"],
                                      markersize=min(style["markersize"], 10), label=style["label"]))
    handles.insert(0, plt.Line2D([0], [0], color="#5B9BD5", linewidth=1.2, label="Mapped river network"))
    minx, miny, maxx, maxy = states.total_bounds
    ax.set_xlim(minx - 0.05, maxx + 0.05)
    ax.set_ylim(miny - 0.05, maxy + 0.05)
    mid_lat = (miny + maxy) / 2
    ax.set_aspect(1 / math.cos(math.radians(mid_lat)))
    ax.set_xlabel("Longitude (\u00b0E)")
    ax.set_ylabel("Latitude (\u00b0N)")
    for _, row in states.iterrows():                          # state names
        pt = row.geometry.representative_point()
        ax.annotate(row["shapeName"], (pt.x, pt.y), ha="center", fontsize=8, color="#333333", style="italic")
    # 50 km scale bar
    km_deg = 50 / (111.32 * math.cos(math.radians(mid_lat)))
    x0, y0 = minx + 0.08, miny + 0.08
    ax.plot([x0, x0 + km_deg], [y0, y0], color="black", linewidth=2, zorder=5)
    ax.text(x0 + km_deg / 2, y0 + 0.03, "50 km", ha="center", fontsize=7, zorder=5)
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False,
              fontsize=7.2, columnspacing=1.2)
    fig.text(0.01, 0.005, SOURCE_LINE, fontsize=5.8, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
