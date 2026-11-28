"""Command-line interface: ``python -m nowri run --mode legacy|state``."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from . import config as C


def _check_env() -> int:
    from .release import collect_versions
    v = collect_versions()
    for k, val in v.items():
        print(f"{k:12s} {val}")
    missing = [m for m in ("geopandas", "shapely", "pyproj", "pyogrio", "requests") if not v.get(m)]
    if missing:
        print("\nMISSING packages:", ", ".join(missing), "\nInstall with: pip install -r requirements.txt")
        return 1
    print("\nEnvironment looks complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nowri", description="NOWRI geospatial screening pipeline")
    p.add_argument("--version", action="version", version=f"nowri {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check-env", help="print software versions and check required packages")

    r = sub.add_parser("run", help="run the pipeline")
    r.add_argument("--mode", choices=["legacy", "state"], required=True,
                   help="legacy = v0.1 box (regression test); state = box from state polygons (corrected)")
    r.add_argument("--workdir", default="data/raw", help="where downloaded source data is cached (git-ignored)")
    r.add_argument("--outdir", default="outputs", help="where GeoPackage and run files are written (git-ignored)")
    r.add_argument("--reports-dir", default="reports", help="small aggregate reports that may be committed")
    r.add_argument("--ogim-path", default=None, help="use an existing local OGIM_v3.0.gpkg (MD5 is verified)")
    r.add_argument("--baseline-gpkg", default=None,
                   help="optional path to the released v0.1 GeoPackage for record-level regression")
    r.add_argument("--margin", type=float, default=C.DEFAULT_MARGIN_DEG,
                   help="degrees added around the state polygons in 'state' mode")
    r.add_argument("--river-source", choices=list(C.RIVER_SOURCES), default="riveratlas",
                   help="river network: riveratlas (default; same reaches as HydroRIVERS, CC BY 4.0) or "
                        "hydrorivers (HydroSHEDS licence)")
    r.add_argument("--riveratlas-zip", default=None,
                   help="use this RiverATLAS shapefile zip (about 2.55 GB) instead of downloading it")
    r.add_argument("--skip-audit", action="store_true", help="skip the OGIM layer coverage audit")

    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "check-env":
        return _check_env()
    from .pipeline import run  # imported late: needs geopandas
    res = run(mode=a.mode, workdir=a.workdir, outdir=a.outdir, reports_dir=a.reports_dir,
              ogim_path=a.ogim_path, baseline_gpkg=a.baseline_gpkg, margin=a.margin,
              skip_audit=a.skip_audit, river_source=a.river_source, riveratlas_zip=a.riveratlas_zip)
    return 0 if res["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
