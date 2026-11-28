import os
import sqlite3
import tempfile
import unittest

import numpy as np
import pandas as pd

import _path  # noqa: F401
from helpers import make_baseline_tables
from nowri import config as C
from nowri import qc, release


def good_df():
    return pd.DataFrame({
        "OGIM_ID": ["a", "b", "c", "d"],
        "SPATIAL_STATE": ["Rivers", "Rivers", "Delta", None],
        "Intersects_mapped_river": [True, False, False, False],
        "Distance_to_river_m": [0.0, 300.0, 3000.0, 8000.0],
        "Distance_band": [C.BAND_INTERSECT, C.BAND_0_1, C.BAND_1_5, None],
        "Distance_band_to_pilot_network": [C.BAND_INTERSECT, C.BAND_0_1, C.BAND_1_5, C.BAND_GT5],
    })


class TestAudit(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(qc.audit_table(good_df(), "x"), [])

    def test_flag_true_distance_nonzero(self):
        df = good_df(); df.loc[0, "Distance_to_river_m"] = 2.0
        self.assertTrue(any("flag=True" in p["problem"] for p in qc.audit_table(df)))

    def test_flag_false_distance_zero(self):
        df = good_df(); df.loc[1, "Distance_to_river_m"] = 0.0
        self.assertTrue(any("flag=False" in p["problem"] for p in qc.audit_table(df)))

    def test_wrong_band(self):
        df = good_df(); df.loc[2, "Distance_band"] = C.BAND_GT5
        self.assertTrue(any("Distance_band !=" in p["problem"] for p in qc.audit_table(df)))

    def test_band_on_unassigned(self):
        df = good_df(); df.loc[3, "Distance_band"] = C.BAND_GT5
        self.assertTrue(any("unassigned" in p["problem"] for p in qc.audit_table(df)))

    def test_null_distance(self):
        df = good_df(); df.loc[2, "Distance_to_river_m"] = np.nan
        self.assertTrue(any("null distance" in p["problem"] for p in qc.audit_table(df)))


class TestBaselineShapedData(unittest.TestCase):
    """Synthetic tables with exactly the documented v0.1 counts must pass every check."""

    def setUp(self):
        self.tables = make_baseline_tables()
        self.summary = qc.summarise(self.tables, C.CORE_LAYER_NAMES)

    def test_all_tables_pass_audit(self):
        for name, df in self.tables.items():
            self.assertEqual(qc.audit_table(df, name), [], name)

    def test_summary_matches_baseline(self):
        river = {"sections_clipped": 5231, "unique_ids_clipped": 5069}
        checks = qc.compare_to_baseline(self.summary, river)
        failed = [c for c in checks if not c["ok"]]
        self.assertEqual(failed, [], failed)
        self.assertTrue(qc.checks_passed(checks))

    def test_regression_detects_change(self):
        s = dict(self.summary)
        s["intersections_total"] = 241
        checks = qc.compare_to_baseline(s, {"sections_clipped": 5231, "unique_ids_clipped": 5069})
        self.assertFalse(qc.checks_passed(checks))
        self.assertIn("intersections_total", [c["check"] for c in checks if not c["ok"]])

    def test_unique_ids(self):
        self.assertEqual(self.summary["unique_ogim_ids_total"], 1008)


class TestRecordLevel(unittest.TestCase):
    def _base_frame(self, tables):
        frames = []
        for layer, df in tables.items():
            d = df[["OGIM_ID", "SPATIAL_STATE", "Intersects_mapped_river",
                    "Distance_band_to_pilot_network"]].copy()
            d["Distance_to_river_km"] = df["Distance_to_river_m"] / 1000
            d["Distance_band"] = df["Distance_band"]
            d.insert(0, "layer", layer)
            frames.append(d)
        return pd.concat(frames, ignore_index=True)

    def setUp(self):
        self.tables = make_baseline_tables()
        # make keys unique within layer for the record-level test
        for layer, df in self.tables.items():
            df["OGIM_ID"] = [f"{layer}-{i}" for i in range(len(df))]
        self.base = self._base_frame(self.tables)

    def test_identical_passes(self):
        res = qc.compare_records(self.tables, self.base)
        self.assertTrue(res["passed"], res)

    def test_flag_mismatch_fails(self):
        t = {k: v.copy() for k, v in self.tables.items()}
        t["pipelines"].loc[0, "Intersects_mapped_river"] = False
        self.assertFalse(qc.compare_records(t, self.base)["passed"])

    def test_band_change_near_edge_is_explained(self):
        t = {k: v.copy() for k, v in self.tables.items()}
        i = t["flaring"].index[t["flaring"]["Distance_band_to_pilot_network"] == C.BAND_0_1][0]
        t["flaring"].loc[i, "Distance_to_river_m"] = 1000.3
        t["flaring"].loc[i, "Distance_band_to_pilot_network"] = C.BAND_1_5
        res = qc.compare_records(t, self.base)
        self.assertEqual(res["band_mismatches"], 1)
        self.assertEqual(res["band_mismatches_explained_by_rounding"], 1)
        self.assertTrue(res["passed"])

    def test_band_change_far_from_edge_is_unexplained(self):
        t = {k: v.copy() for k, v in self.tables.items()}
        i = t["flaring"].index[t["flaring"]["Distance_band_to_pilot_network"] == C.BAND_0_1][0]
        t["flaring"].loc[i, "Distance_to_river_m"] = 3000.0
        t["flaring"].loc[i, "Distance_band_to_pilot_network"] = C.BAND_1_5
        res = qc.compare_records(t, self.base)
        self.assertEqual(res["band_mismatches_unexplained"], 1)
        self.assertFalse(res["passed"])

    def test_missing_record_fails(self):
        t = {k: v.copy() for k, v in self.tables.items()}
        t["wells"] = t["wells"].iloc[1:]
        res = qc.compare_records(t, self.base)
        self.assertEqual(res["only_in_base"], 1)
        self.assertFalse(res["passed"])

    def test_read_baseline_gpkg_via_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.gpkg")
            con = sqlite3.connect(p)
            con.execute('CREATE TABLE "wells" (fid INTEGER, OGIM_ID TEXT, SPATIAL_STATE TEXT, '
                        'Intersects_mapped_river INTEGER, Distance_to_river_km REAL, '
                        'Distance_band TEXT, Distance_band_to_pilot_network TEXT)')
            con.execute("INSERT INTO wells VALUES (1,'7',NULL,0,12.5,NULL,'>5 km')")
            con.commit(); con.close()
            df = qc.read_baseline_gpkg(p, layers=["wells", "not_a_layer"])
            self.assertEqual(len(df), 1)
            self.assertEqual(df.loc[0, "layer"], "wells")
            self.assertEqual(df.loc[0, "OGIM_ID"], "7")


class TestBaselineReaderRobustness(unittest.TestCase):
    def test_layer_without_spatial_state_column(self):
        """The real v0.1 'wells' layer has no SPATIAL_STATE column."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.gpkg")
            con = sqlite3.connect(p)
            con.execute('CREATE TABLE "wells" (fid INTEGER, OGIM_ID TEXT, Intersects_mapped_river INTEGER, '
                        'Distance_to_river_km REAL, Distance_band_to_pilot_network TEXT)')
            con.execute("INSERT INTO wells VALUES (1,'7',0,12.5,'>5 km')")
            con.commit(); con.close()
            df = qc.read_baseline_gpkg(p, layers=["wells"])
            self.assertIn("SPATIAL_STATE", df.columns)
            self.assertIn("Distance_band", df.columns)
            self.assertTrue(df["SPATIAL_STATE"].isna().all())


class TestPlaceholdersAndSensitivity(unittest.TestCase):
    def test_placeholder_counts(self):
        df = pd.DataFrame({
            "a": ["N/A", "x", None, " n/a "],
            "b": [-999, 1, 2, np.nan],
            "c": ["1900-01-01", "2020-01-01", None, "1900-01-01T00:00:00"],
            "geometry": ["g"] * 4,
        })
        c = qc.placeholder_counts(df)
        self.assertEqual(c["literal_NA_occurrences"], 2)
        self.assertEqual(c["numeric_minus_999_sentinels"], 1)
        self.assertEqual(c["placeholder_dates_1900_01_01"], 2)
        self.assertEqual(c["actual_null_cells"], 3)

    def test_network_sensitivity(self):
        df = good_df()
        df["Distance_to_unclipped_network_m"] = [0.0, 300.0, 400.0, 8000.0]  # row 2: 1-5 km -> >0-1 km
        df["Intersects_unclipped_network"] = [True, False, False, False]
        res = qc.network_sensitivity({"x": df})
        self.assertEqual(int(res.loc[0, "assigned_records"]), 3)
        self.assertEqual(int(res.loc[0, "band_changed_vs_clipped"]), 1)


class TestRelease(unittest.TestCase):
    def test_data_dictionary_describes_everything(self):
        df = good_df()
        df["MMCF_2020"] = [1.0, -999.0, 2.0, 3.0]
        df["FAC_STATUS"] = ["N/A"] * 4
        dd = release.build_data_dictionary({"x": df})
        self.assertTrue((dd["Description"].str.len() > 0).all())
        row = dd[dd["Field"] == "FAC_STATUS"].iloc[0]
        self.assertEqual(int(row["Placeholder_values"]), 4)
        self.assertEqual(int(row["Informative_values"]), 0)
        self.assertEqual(int(dd[dd["Field"] == "MMCF_2020"].iloc[0]["Placeholder_values"]), 1)

    def test_manifest_and_summary_render(self):
        tables = make_baseline_tables()
        summary = qc.summarise(tables, C.CORE_LAYER_NAMES)
        checks = qc.compare_to_baseline(summary, {"sections_clipped": 5231, "unique_ids_clipped": 5069})
        m = release.build_manifest(
            run_id="legacy_test", mode="legacy", bbox=C.LEGACY_BBOX, margin_deg=0.25,
            analysis_crs=C.ANALYSIS_CRS,
            sources=[{"name": "OGIM", "version": "v3.0", "licence_recorded": "test"}],
            outputs=[], summary={**summary, "extras": None, "river_network": {}}, audit_problems=0,
            regression={"passed": True}, record_level=None, extra_layers=[],
            placeholders={"literal_NA_occurrences": 0}, versions={"python": "x"}, commit=None)
        self.assertEqual(m["mode"], "legacy")
        self.assertIn("redistribution_note", m)
        md = release.render_run_summary(m, checks, None, None, None)
        self.assertIn("1032", md)
        self.assertIn("PASS", md)

    def test_sha256(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"abc"); name = f.name
        try:
            self.assertEqual(release.sha256_file(name),
                             "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        finally:
            os.remove(name)


if __name__ == "__main__":
    unittest.main()


class TestSourcesAndRendering(unittest.TestCase):
    def test_licence_parsing_variants(self):
        from nowri.sources import _licence_from_zenodo as lic
        self.assertEqual(lic({"license": {"id": "cc-by-4.0"}}), "cc-by-4.0")
        self.assertEqual(lic({"license": "CC-BY-4.0"}), "CC-BY-4.0")
        self.assertEqual(lic({"rights": [{"title": {"en": "Creative Commons Attribution 4.0"}}]}),
                         "Creative Commons Attribution 4.0")
        self.assertIn("NOT FOUND", lic({}))

    def test_full_summary_render(self):
        import pandas as pd
        from nowri import proximity
        tables = make_baseline_tables()
        summary = qc.summarise(tables, C.CORE_LAYER_NAMES)
        checks = qc.compare_to_baseline(summary, {"sections_clipped": 1, "unique_ids_clipped": 1})  # deliberate fail
        tol = proximity.tolerance_table([True, False], [0.0, 50.0])
        cov = pd.DataFrame([{"ogim_layer": "LNG_Facilities", "nigerian_records_in_box": 3,
                             "nigerian_records_in_legacy_box": 0, "error": ""}])
        m = release.build_manifest(
            run_id="r", mode="state", bbox=(1, 2, 3, 4), margin_deg=0.25, analysis_crs=C.ANALYSIS_CRS,
            sources=[{"name": "OGIM", "version": "v3.0", "licence_recorded": "cc-by-4.0"}], outputs=[],
            summary={**summary, "extras": None, "river_network": {}}, audit_problems=0, regression=None,
            record_level={"passed": True, "only_in_new": 0, "only_in_base": 0,
                          "intersection_flag_mismatches": 0, "band_mismatches": 0,
                          "band_mismatches_explained_by_rounding": 0, "band_mismatches_unexplained": 0},
            extra_layers=["lng"], placeholders={}, versions={}, commit="abc")
        md = release.render_run_summary(m, checks, m["record_level_regression_vs_v0_1"], tol, cov)
        for needle in ("Change relative to the documented v0.1 baseline", "informational", "not a test",
                       "LNG_Facilities", "Tolerance sensitivity", "cc-by-4.0",
                       "Extra layers included: lng", "Record-level regression"):
            self.assertIn(needle, md)
        self.assertNotIn("FAIL", md.replace("Record-level regression vs v0.1 GeoPackage: PASS", ""))

    def test_legacy_mode_still_reports_pass_or_fail(self):
        tables = make_baseline_tables()
        summary = qc.summarise(tables, C.CORE_LAYER_NAMES)
        good = qc.compare_to_baseline(summary, {"sections_clipped": 5231, "unique_ids_clipped": 5069})
        bad = qc.compare_to_baseline(summary, {"sections_clipped": 1, "unique_ids_clipped": 1})
        def render(checks):
            m = release.build_manifest(
                run_id="r", mode="legacy", bbox=C.LEGACY_BBOX, margin_deg=0.25, analysis_crs=C.ANALYSIS_CRS,
                sources=[], outputs=[], summary={**summary, "extras": None, "river_network": {}},
                audit_problems=0, regression=None, record_level=None, extra_layers=[], placeholders={},
                versions={}, commit=None)
            return release.render_run_summary(m, checks, None, None, None)
        self.assertIn("PASS (41/41 checks passed)", render(good))
        out = render(bad)
        self.assertIn("FAIL", out)
        self.assertIn("MISMATCH river_sections_clipped", out)
