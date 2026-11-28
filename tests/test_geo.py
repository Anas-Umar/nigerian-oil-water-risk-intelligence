"""Geometry tests on small synthetic examples.

Skipped automatically when geopandas is not installed. They are run in Colab (and CI)
before the long pipeline run so that environment or API problems show up in seconds.
"""
import unittest

import _path  # noqa: F401

try:
    import geopandas as gpd
    import numpy as np
    import pandas as pd
    from shapely.geometry import LineString, Point, box
    HAVE_GEO = True
except Exception:  # pragma: no cover
    HAVE_GEO = False

if HAVE_GEO:
    from nowri import config as C
    from nowri import pipeline as PL


@unittest.skipUnless(HAVE_GEO, "geopandas not installed")
class TestProximity(unittest.TestCase):
    def setUp(self):
        # Two parallel rivers, 600 m apart, in the analysis CRS (metres).
        self.rivers = gpd.GeoDataFrame(
            {"HYRIV_ID": [1, 2]},
            geometry=[LineString([(0, 0), (1000, 0)]), LineString([(0, 600), (1000, 600)])],
            crs=C.ANALYSIS_CRS)

    def _assets(self, geoms):
        return gpd.GeoDataFrame(geometry=geoms, crs=C.ANALYSIS_CRS)

    def test_distance_flag_and_ties(self):
        a = self._assets([Point(500, 0),          # on river 1
                          Point(500, 100),        # 100 m from river 1
                          Point(500, 300),        # equidistant: tie between rivers 1 and 2
                          Point(500, -2000)])     # 2 km south
        out = PL.compute_proximity(a, self.rivers)
        self.assertEqual(list(out["intersects"]), [True, False, False, False])
        np.testing.assert_allclose(out["dist_m"].to_numpy(), [0.0, 100.0, 300.0, 2000.0], atol=1e-6)
        self.assertEqual(list(out["matches"]), [1, 1, 2, 1])

    def test_polygon_touching_river_intersects(self):
        a = self._assets([box(400, -10, 600, 10), box(400, 100, 600, 200)])
        out = PL.compute_proximity(a, self.rivers)
        self.assertEqual(list(out["intersects"]), [True, False])
        self.assertEqual(float(out.loc[0, "dist_m"]), 0.0)
        self.assertAlmostEqual(float(out.loc[1, "dist_m"]), 100.0, places=6)

    def test_sub_millimetre_gap_is_not_an_intersection(self):
        """The v0.1 two-station case: a 0.0003 m gap must stay non-intersecting."""
        r = gpd.GeoDataFrame({"HYRIV_ID": [9]}, geometry=[LineString([(0, 0.0003), (1000, 0.0003)])],
                             crs=C.ANALYSIS_CRS)
        out = PL.compute_proximity(self._assets([Point(500, 0)]), r)
        self.assertFalse(bool(out.loc[0, "intersects"]))
        self.assertGreater(float(out.loc[0, "dist_m"]), 0.0)
        self.assertLess(float(out.loc[0, "dist_m"]), 0.001)


@unittest.skipUnless(HAVE_GEO, "geopandas not installed")
class TestStatesAndClipping(unittest.TestCase):
    def setUp(self):
        self.states = gpd.GeoDataFrame(
            {"shapeName": ["Bayelsa", "Rivers"]},
            geometry=[box(5.0, 5.0, 5.5, 5.5), box(5.5, 5.0, 6.0, 5.5)], crs=4326)

    def test_extraction_bbox(self):
        self.assertEqual(PL.extraction_bbox("legacy", self.states, 0.25), C.LEGACY_BBOX)
        self.assertEqual(PL.extraction_bbox("state", self.states, 0.25), (4.75, 4.75, 6.25, 5.75))
        with self.assertRaises(ValueError):
            PL.extraction_bbox("bogus", self.states, 0.25)

    def test_assign_points(self):
        pts = gpd.GeoDataFrame({"OGIM_ID": ["a", "b", "c"]},
                               geometry=[Point(5.2, 5.2), Point(5.8, 5.2), Point(7.0, 5.2)], crs=4326)
        out, n_dup = PL.assign_points(pts, self.states)
        self.assertEqual(n_dup, 0)
        self.assertEqual(len(out), 3)
        self.assertEqual(out.loc[0, "SPATIAL_STATE"], "Bayelsa")
        self.assertEqual(out.loc[1, "SPATIAL_STATE"], "Rivers")
        self.assertTrue(pd.isna(out.loc[2, "SPATIAL_STATE"]))

    def test_line_is_split_between_states(self):
        line = gpd.GeoDataFrame({"OGIM_ID": ["p1"]},
                                geometry=[LineString([(5.1, 5.25), (5.9, 5.25)])], crs=4326)
        for strict in (False, True):
            out, dropped = PL.prepare_lines(line, self.states, (4.0, 4.0, 7.0, 7.0), strict)
            self.assertEqual(sorted(out["SPATIAL_STATE"]), ["Bayelsa", "Rivers"])
            self.assertEqual(len(out["Section_ID"].unique()), 2)
            total_km = PL._geodesic_length(line.geometry.iloc[0]) / 1000.0
            self.assertAlmostEqual(float(out["CLIPPED_LENGTH_KM"].sum()), total_km, delta=0.1)
            self.assertTrue(((out["CLIPPED_LENGTH_KM"] > 40) & (out["CLIPPED_LENGTH_KM"] < 48)).all())

    def test_line_cut_by_box_edge(self):
        """The legacy-box failure mode: a box edge inside a state removes the part beyond it."""
        line = gpd.GeoDataFrame({"OGIM_ID": ["p1"]},
                                geometry=[LineString([(5.6, 5.25), (5.95, 5.25)])], crs=4326)
        cut, _ = PL.prepare_lines(line, self.states, (4.0, 4.0, 5.8, 7.0), True)
        full, _ = PL.prepare_lines(line, self.states, (4.0, 4.0, 7.0, 7.0), True)
        self.assertLess(float(cut["CLIPPED_LENGTH_KM"].sum()), float(full["CLIPPED_LENGTH_KM"].sum()) * 0.7)

    def test_polygon_split(self):
        poly = gpd.GeoDataFrame({"OGIM_ID": ["f1"]}, geometry=[box(5.4, 5.1, 5.6, 5.3)], crs=4326)
        out, _ = PL.prepare_polygons(poly, self.states, True)
        self.assertEqual(sorted(out["SPATIAL_STATE"]), ["Bayelsa", "Rivers"])
        a = out["CLIPPED_AREA_KM2"].to_numpy()
        self.assertAlmostEqual(float(a[0]), float(a[1]), delta=0.02 * float(a.max()))


@unittest.skipUnless(HAVE_GEO, "geopandas not installed")
class TestBuildLayer(unittest.TestCase):
    def test_assigned_vs_unassigned_bands(self):
        spec = C.CORE_LAYERS[6]  # stations (point layer)
        self.assertEqual(spec.kind, "point")
        # river through the centre of the analysis CRS; one assigned point 300 m away,
        # one unassigned point 8 km away.
        rivers_m = gpd.GeoDataFrame({"HYRIV_ID": [1]}, geometry=[LineString([(-20000, 0), (20000, 0)])],
                                    crs=C.ANALYSIS_CRS)
        pts_m = gpd.GeoDataFrame(geometry=[Point(0, 300), Point(0, 8000)], crs=C.ANALYSIS_CRS)
        pts = pts_m.to_crs(4326)
        pts["OGIM_ID"] = ["a", "b"]
        pts["STATE_PROV"] = ["RIVERS", "IMO"]
        pts["FAC_TYPE"] = ["FLOW STATION", None]
        pts["SPATIAL_STATE"] = ["Rivers", np.nan]
        out = PL.build_layer_gdf(spec, pts, rivers_m, rivers_m)
        self.assertEqual(out.loc[0, "Distance_band"], C.BAND_0_1)
        self.assertIsNone(out.loc[1, "Distance_band"])
        self.assertEqual(out.loc[1, "Distance_band_to_pilot_network"], C.BAND_GT5)
        self.assertEqual(list(out["Location_assignment"]), [C.LOC_ASSIGNED, C.LOC_UNASSIGNED])
        self.assertEqual(list(out["State_attribute_conflict"]), [False, False])
        self.assertEqual(out.loc[1, "Asset_subtype"], "N/A")
        self.assertAlmostEqual(float(out.loc[0, "Distance_to_river_m"]), 300.0, delta=0.5)

    def test_state_conflict_detection(self):
        got = PL.state_attribute_conflict(pd.Series(["RIVERS", "IMO STATE", "N/A", "DELTA"]),
                                          pd.Series(["Bayelsa", "Rivers", "Rivers", np.nan]))
        self.assertEqual(list(got), [True, True, False, False])


@unittest.skipUnless(HAVE_GEO, "geopandas not installed")
class TestProjectionCheckAndMap(unittest.TestCase):
    def setUp(self):
        # Two parallel rivers 600 m apart; points placed in the analysis CRS then stored in EPSG:4326.
        self.rivers_m = gpd.GeoDataFrame(
            {"HYRIV_ID": [1, 2]},
            geometry=[LineString([(-20000, 0), (20000, 0)]), LineString([(-20000, 600), (20000, 600)])],
            crs=C.ANALYSIS_CRS)
        pts_m = gpd.GeoDataFrame(geometry=[Point(0, 100), Point(5000, 300), Point(-8000, -2000)], crs=C.ANALYSIS_CRS)
        pts = pts_m.to_crs(4326)
        pts["OGIM_ID"] = ["a", "b", "c"]
        pts["Distance_to_river_m"] = [100.0, 300.0, 2000.0]
        self.tables = {"flaring": pts}

    def test_projection_check_on_synthetic_points(self):
        from nowri import projection_check as PC
        details, summary = PC.projection_check(self.tables, self.rivers_m)
        self.assertEqual(len(details), 3)
        self.assertLess(float(details["difference_m"].max()), 0.05)        # AEQD barely distorts at these ranges
        tie = details[details["OGIM_ID"] == "b"].iloc[0]
        self.assertEqual(int(tie["n_tied_matches"]), 2)                    # equidistant between the two rivers
        self.assertTrue(bool(details["stored_matches"].all()))
        self.assertEqual(summary["sample_size"], 3)
        self.assertEqual(summary["tied_nearest_river_records"], 1)

    def test_study_area_map_is_written(self):
        import os, tempfile
        from shapely.geometry import box as _box
        from nowri import figures
        states = gpd.GeoDataFrame({"shapeName": ["Bayelsa", "Rivers"]},
                                  geometry=[_box(5.0, 4.5, 5.6, 5.0), _box(5.6, 4.5, 6.2, 5.0)], crs=4326)
        rivers = gpd.GeoDataFrame({"HYRIV_ID": [1]}, geometry=[LineString([(5.0, 4.7), (6.2, 4.8)])], crs=4326)
        flares = gpd.GeoDataFrame({"SPATIAL_STATE": ["Rivers", None]},
                                  geometry=[Point(5.8, 4.7), Point(7.0, 4.7)], crs=4326)
        lines = gpd.GeoDataFrame({"SPATIAL_STATE": ["Bayelsa"]}, geometry=[LineString([(5.1, 4.6), (5.5, 4.9)])], crs=4326)
        fields = gpd.GeoDataFrame({"SPATIAL_STATE": ["Bayelsa"]}, geometry=[_box(5.2, 4.6, 5.3, 4.7)], crs=4326)
        with tempfile.TemporaryDirectory() as d:
            out = figures.fig_study_area_map(states, rivers, {"flaring": flares, "pipelines": lines,
                                                              "oil_gas_fields": fields}, os.path.join(d, "m.png"), dpi=60)
            self.assertGreater(os.path.getsize(out), 5000)


if __name__ == "__main__":
    unittest.main()
