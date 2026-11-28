# reports/

Small **aggregate** outputs of pipeline runs that are safe to version-control:
run summaries, manifests, counts, sensitivity tables and a data dictionary without
example values. No third-party records or geometries belong here.

- `legacy/`  regression run with the original v0.1 extraction box
- `state/`   corrected run with the extraction box taken from the state polygons

The GeoPackage and other record-level outputs are written to `outputs/` and are git-ignored.
