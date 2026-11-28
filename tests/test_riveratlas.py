import os
import tempfile
import unittest
import zipfile

import _path  # noqa: F401
from nowri import cli, config as C, release, sources


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


AF = ["shp", "shx", "dbf", "prj", "cpg"]


class TestTileSelection(unittest.TestCase):
    def test_select_members(self):
        names = ["a/RiverATLAS_v10_af.shp", "a/RiverATLAS_v10_af.dbf", "a/RiverATLAS_v10_as.shp",
                 "a/RiverATLAS_v10_af.shp.xml", "b/BasinATLAS_v10_af.shp", "RiverATLAS_Data_v10.pdf"]
        got = sources.select_zip_members(names, C.RIVERATLAS_TILE_PATTERN)
        self.assertEqual(got, ["a/RiverATLAS_v10_af.dbf", "a/RiverATLAS_v10_af.shp"])

    def test_extract_only_africa_from_flat_and_foldered_zip(self):
        with tempfile.TemporaryDirectory() as d:
            files = {f"RiverATLAS_v10_shp/RiverATLAS_v10_af.{e}": b"x" for e in AF}
            files.update({f"RiverATLAS_v10_shp/RiverATLAS_v10_eu.{e}": b"x" for e in AF})
            zp = os.path.join(d, "r.zip")
            make_zip(zp, files)
            out = sources.extract_tiles(zp, os.path.join(d, "out"), C.RIVERATLAS_TILE_PATTERN)
            self.assertEqual([os.path.basename(p) for p in out], ["RiverATLAS_v10_af.shp"])
            self.assertTrue(all(os.path.exists(p) for p in out))
            self.assertFalse(os.path.exists(os.path.join(d, "out", "RiverATLAS_v10_shp", "RiverATLAS_v10_eu.shp")))
            self.assertTrue(os.path.exists(os.path.join(d, "out", "RiverATLAS_v10_shp", "RiverATLAS_v10_af.dbf")))

    def test_split_north_south_tiles_are_both_returned(self):
        with tempfile.TemporaryDirectory() as d:
            files = {}
            for tile in ("af_north", "af_south"):
                files.update({f"RiverATLAS_v10_{tile}.{e}": b"x" for e in AF})
            zp = os.path.join(d, "r.zip")
            make_zip(zp, files)
            out = sources.extract_tiles(zp, os.path.join(d, "out"), C.RIVERATLAS_TILE_PATTERN)
            self.assertEqual(len(out), 2)

    def test_zip_inside_zip(self):
        with tempfile.TemporaryDirectory() as d:
            inner = os.path.join(d, "inner.zip")
            make_zip(inner, {f"RiverATLAS_v10_af.{e}": b"x" for e in AF})
            outer = os.path.join(d, "outer.zip")
            with zipfile.ZipFile(outer, "w") as z:
                z.write(inner, "RiverATLAS_v10_shp.zip")
                z.writestr("README.txt", "x")
            out = sources.extract_tiles(outer, os.path.join(d, "out"), C.RIVERATLAS_TILE_PATTERN)
            self.assertEqual([os.path.basename(p) for p in out], ["RiverATLAS_v10_af.shp"])

    def test_no_match_gives_helpful_error(self):
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "r.zip")
            make_zip(zp, {"RiverATLAS_v10_eu.shp": b"x", "other.txt": b"y"})
            with self.assertRaises(FileNotFoundError) as cm:
                sources.extract_tiles(zp, os.path.join(d, "out"), C.RIVERATLAS_TILE_PATTERN)
            self.assertIn("RiverATLAS_v10_eu.shp", str(cm.exception))

    def test_fetch_uses_existing_tiles_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            tile_dir = os.path.join(d, "riveratlas", "sub")
            os.makedirs(tile_dir)
            open(os.path.join(tile_dir, "RiverATLAS_v10_af.shp"), "wb").close()
            info = sources.fetch_riveratlas(d)
            self.assertEqual(info["tiles"], ["RiverATLAS_v10_af.shp"])
            self.assertIn("CC BY 4.0", info["licence_recorded"])
            self.assertNotIn("paths", sources.public_source_record(info))


class TestOptionsAndNotes(unittest.TestCase):
    def test_cli_accepts_river_source(self):
        p = cli.build_parser()
        a = p.parse_args(["run", "--mode", "legacy", "--river-source", "riveratlas"])
        self.assertEqual(a.river_source, "riveratlas")
        self.assertEqual(p.parse_args(["run", "--mode", "state"]).river_source, "riveratlas")
        self.assertEqual(p.parse_args(["run", "--mode", "state", "--river-source", "hydrorivers"]).river_source,
                         "hydrorivers")
        with self.assertRaises(SystemExit):
            p.parse_args(["run", "--mode", "state", "--river-source", "bogus"])

    def test_manifest_note_depends_on_river_source(self):
        common = dict(run_id="r", mode="state", bbox=C.LEGACY_BBOX, margin_deg=0.25, analysis_crs=C.ANALYSIS_CRS,
                      sources=[], outputs=[], summary={"records_by_layer": {}}, audit_problems=0)
        ra = release.build_manifest(river_source="riveratlas", **common)
        hr = release.build_manifest(**common)
        self.assertIn("RiverATLAS", ra["redistribution_note"])
        self.assertEqual(ra["parameters"]["river_source"], "riveratlas")
        self.assertIn("HydroRIVERS", hr["redistribution_note"])
        self.assertEqual(hr["parameters"]["river_source"], "hydrorivers")


if __name__ == "__main__":
    unittest.main()
