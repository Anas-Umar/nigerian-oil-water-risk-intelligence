import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import _path  # noqa: F401
from helpers import make_baseline_tables
from nowri import config as C, qc, release


class TestFigures(unittest.TestCase):
    def test_bar_charts_are_written_and_valid_png(self):
        from nowri import figures
        summary = qc.summarise(make_baseline_tables(), C.CORE_LAYER_NAMES)
        with tempfile.TemporaryDirectory() as d:
            a = figures.fig_bands_by_category(summary, os.path.join(d, "a.png"), dpi=80)
            b = figures.fig_bands_by_state(summary, os.path.join(d, "b.png"), dpi=80)
            for p in (a, b):
                with open(p, "rb") as f:
                    self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
                self.assertGreater(os.path.getsize(p), 8000)

    def test_charts_survive_a_missing_layer_and_zero_bands(self):
        from nowri import figures
        tables = make_baseline_tables()
        del tables["refineries"]
        summary = qc.summarise(tables, [n for n in C.CORE_LAYER_NAMES if n in tables])
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(os.path.exists(figures.fig_bands_by_category(summary, os.path.join(d, "a.png"), dpi=60)))


class TestProjectionStats(unittest.TestCase):
    def _details(self):
        return pd.DataFrame([
            dict(layer="a", n_tied_matches=1, geodesic_distance_m=100.0, projected_distance_m=100.001,
                 difference_m=0.001, difference_percent=0.001, stored_matches=True),
            dict(layer="a", n_tied_matches=2, geodesic_distance_m=0.0, projected_distance_m=0.0,
                 difference_m=0.0, difference_percent=np.nan, stored_matches=True),
            dict(layer="b", n_tied_matches=1, geodesic_distance_m=50.0, projected_distance_m=50.003,
                 difference_m=0.003, difference_percent=0.006, stored_matches=True),
            dict(layer="b", n_tied_matches=1, geodesic_distance_m=20.0, projected_distance_m=20.0,
                 difference_m=0.0, difference_percent=0.0, stored_matches=False),
        ])

    def test_statistics_use_non_zero_records_only(self):
        s = qc.summarise_projection_check(self._details())
        self.assertEqual((s["sample_size"], s["layers_represented"]), (4, 2))
        self.assertEqual((s["tied_nearest_river_records"], s["zero_distance_records"], s["nonzero_distance_records"]),
                         (1, 1, 3))
        self.assertAlmostEqual(s["mean_absolute_difference_m"], (0.001 + 0.003 + 0.0) / 3)
        self.assertAlmostEqual(s["maximum_absolute_difference_m"], 0.003)
        self.assertAlmostEqual(s["mean_difference_percent"], (0.001 + 0.006 + 0.0) / 3)
        self.assertAlmostEqual(s["maximum_difference_percent"], 0.006)
        self.assertEqual((s["stored_distances_matching"], s["stored_distances_mismatching"]), (3, 1))

    def test_all_zero_distance_sample_does_not_crash(self):
        d = self._details().iloc[[1]]
        s = qc.summarise_projection_check(d)
        self.assertEqual(s["nonzero_distance_records"], 0)
        self.assertTrue(np.isnan(s["mean_absolute_difference_m"]))

    def test_summary_section_rendered_and_error_case(self):
        tables = make_baseline_tables()
        summary = qc.summarise(tables, C.CORE_LAYER_NAMES)
        common = dict(run_id="r", mode="state", bbox=C.LEGACY_BBOX, margin_deg=0.25, analysis_crs=C.ANALYSIS_CRS,
                      sources=[], outputs=[], summary={**summary, "extras": None, "river_network": {}},
                      audit_problems=0)
        ok = release.build_manifest(projection_check=qc.summarise_projection_check(self._details()), **common)
        md = release.render_run_summary(ok, None, None, None, None)
        self.assertIn("## Projection sensitivity (sample of 4 records", md)
        self.assertIn("non-zero-distance records only", md)
        bad = release.build_manifest(projection_check={"error": "boom"}, **common)
        self.assertIn("NOT COMPUTED (boom)", release.render_run_summary(bad, None, None, None, None))


if __name__ == "__main__":
    unittest.main()
