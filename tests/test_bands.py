import unittest

import numpy as np

import _path  # noqa: F401
from nowri import config as C
from nowri import proximity as P


class TestBands(unittest.TestCase):
    def test_edges(self):
        d = [0.0, 0.0003, 1.0, 1000.0, 1000.0001, 5000.0, 5000.5]
        f = [True, False, False, False, False, False, False]
        got = list(P.classify_bands(f, d))
        self.assertEqual(got, [C.BAND_INTERSECT, C.BAND_0_1, C.BAND_0_1, C.BAND_0_1,
                               C.BAND_1_5, C.BAND_1_5, C.BAND_GT5])

    def test_two_station_regression(self):
        """v0.1 flagged a 0.000297 m gap as 'intersecting' because km was rounded to 3 d.p."""
        d_m = 0.000297
        self.assertEqual(float(P.round_km([d_m])[0]), 0.0)          # rounding hides it...
        self.assertEqual(P.classify_bands([False], [d_m])[0], C.BAND_0_1)  # ...classification must not

    def test_nan_distance_is_none_unless_intersecting(self):
        got = P.classify_bands([False, True], [np.nan, np.nan])
        self.assertIsNone(got[0])
        self.assertEqual(got[1], C.BAND_INTERSECT)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            P.classify_bands([True], [0.0, 1.0])

    def test_band_counts_include_zero_bands(self):
        c = P.band_counts([C.BAND_0_1, C.BAND_0_1, None])
        self.assertEqual(c[C.BAND_0_1], 2)
        self.assertEqual(c[C.BAND_GT5], 0)
        self.assertEqual(set(c), set(C.BAND_LABELS))

    def test_tolerance_table_monotonic(self):
        flags = [True, False, False, False, False]
        d = [0.0, 5.0, 50.0, 400.0, 6000.0]
        t = P.tolerance_table(flags, d, tolerances_m=(0, 10, 100, 1000))
        n = list(t["records_intersecting_or_within"])
        self.assertEqual(n, [1, 2, 3, 4])
        self.assertTrue(all(b >= a for a, b in zip(n, n[1:])))


class TestConfig(unittest.TestCase):
    def test_crs_string_is_documented_aeqd(self):
        self.assertIn("+proj=aeqd", C.ANALYSIS_CRS)
        self.assertIn("+lat_0=5.25", C.ANALYSIS_CRS)
        self.assertIn("+lon_0=5.75", C.ANALYSIS_CRS)
        self.assertNotIn("utm", C.ANALYSIS_CRS.lower())

    def test_legacy_box_documented(self):
        self.assertEqual(C.LEGACY_BBOX, (4.5, 4.0, 7.0, 6.5))

    def test_baseline_internally_consistent(self):
        b = C.BASELINE_V01
        self.assertEqual(sum(b["records_by_layer"].values()), b["total_records"])
        self.assertEqual(sum(b["assigned_by_layer"].values()), b["assigned_total"])
        self.assertEqual(b["total_records"] - b["assigned_total"], b["unassigned_total"])
        self.assertEqual(sum(b["intersections_by_layer"].values()), b["intersections_total"])
        self.assertEqual(sum(b["bands_assigned"].values()), b["assigned_total"])
        self.assertEqual(sum(b["records_by_state"].values()), b["assigned_total"])

    def test_layer_names_unique(self):
        names = [s.name for s in C.CORE_LAYERS] + [s.name for s in C.EXTRA_LAYERS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(C.CORE_LAYERS), 9)


if __name__ == "__main__":
    unittest.main()
