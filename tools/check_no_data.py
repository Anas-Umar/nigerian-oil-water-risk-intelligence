#!/usr/bin/env python3
"""Fail if third-party data (or oversized files) are about to enter version control.

Used by the git pre-commit hook and by CI. Checks tracked files (``git ls-files``)
or, with --staged, the files staged for commit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

FORBIDDEN_SUFFIXES = {
    ".gpkg", ".shp", ".shx", ".dbf", ".prj", ".cpg", ".geojson", ".kml", ".kmz",
    ".tif", ".tiff", ".nc", ".zip", ".7z", ".rar", ".gz", ".tar", ".parquet",
    ".feather", ".sqlite", ".db", ".gdb",
}
MAX_BYTES = 5 * 1024 * 1024          # any single file
MAX_NOTEBOOK_BYTES = 1 * 1024 * 1024  # notebooks should be stored without outputs


def listed_files(staged: bool):
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"] if staged else ["git", "ls-files"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.strip()]


def main() -> int:
    staged = "--staged" in sys.argv
    problems = []
    for path in listed_files(staged):
        if not os.path.exists(path):
            continue
        suffix = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        if suffix in FORBIDDEN_SUFFIXES:
            problems.append(f"{path}: forbidden data/archive file type ({suffix})")
        if size > MAX_BYTES:
            problems.append(f"{path}: {size/1e6:.1f} MB exceeds the {MAX_BYTES/1e6:.0f} MB limit")
        if suffix == ".ipynb":
            if size > MAX_NOTEBOOK_BYTES:
                problems.append(f"{path}: notebook is {size/1e6:.1f} MB; clear outputs before committing")
            try:
                with open(path, encoding="utf-8") as f:
                    nb = json.load(f)
                n_out = sum(len(c.get("outputs", [])) for c in nb.get("cells", []) if c.get("cell_type") == "code")
                if n_out:
                    problems.append(f"{path}: notebook contains {n_out} stored outputs; clear outputs before committing")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{path}: cannot parse notebook ({exc})")
    if problems:
        print("DATA POLICY CHECK FAILED (see DATA_POLICY.md):")
        for p in problems:
            print("  -", p)
        return 1
    print("Data policy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
