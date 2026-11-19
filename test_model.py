import json
import math
import tempfile
import unittest
from pathlib import Path

import cadquery as cq

from build_model import (
    ROOT, flange_z_at_level, floor_frame, make_parts,
    validate_features, validate_floor_geometry,
)
from measurements import bolt_spacings, extract_edges, write_measurements


class MeasurementTests(unittest.TestCase):
    def test_bolt_spacings_follow_perimeter_not_image_scan_order(self):
        holes = [(9, 7), (1, 1), (1, 7), (9, 1)]
        p = {"engine_roll_deg": -15, "front_depth_mm": 142}
        floor = [floor_frame((*point, 0), p) for point in holes]
        spacings = bolt_spacings(holes, floor, [(0, 0), (10, 0), (10, 8), (0, 8)], 100)
        self.assertEqual(len(spacings), 4)
        for actual, expected in zip(spacings, [8, 6, 8, 6]):
            self.assertAlmostEqual(actual["length_mm"], expected)
        self.assertEqual(spacings[-1]["hole_ids"], [4, 1])
        self.assertEqual(spacings[-1]["points"][1], spacings[0]["points"][0])
        self.assertEqual([spacing["id"] for spacing in spacings], [100, 101, 102, 103])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_measurements([], output, spacings)
            self.assertIn("4,1,6.000000", (output / "bolt_spacings.csv").read_text())

    def test_lengths_use_3d_geometry_and_closed_curve_length(self):
        line = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(3, 0, 4))
        circle = cq.Edge.makeCircle(3).rotate((0, 0, 0), (1, 0, 0), -15).translate((10, 20, 30))
        edges = extract_edges([
            ("sloped", cq.Workplane("XY").add(line), (1, 1, 1)),
            ("round", cq.Workplane("XY").add(circle), (1, 1, 1)),
        ])
        self.assertAlmostEqual(edges[0]["length_mm"], 5)
        self.assertAlmostEqual(edges[1]["length_mm"], 6 * math.pi)
        self.assertAlmostEqual(edges[1]["radius_mm"], 3)
        self.assertEqual(edges[1]["points"][0], edges[1]["points"][-1])
        self.assertGreater(len(edges[1]["points"]), 12)
        self.assertEqual([edge["id"] for edge in edges], [1, 2])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_measurements(edges, output)
            saved = json.loads((output / "edge_measurements.json").read_text())
            self.assertEqual(saved["edges"], edges)
            self.assertIn("18.849556", (output / "edge_lengths.csv").read_text())


class FloorGeometryTests(unittest.TestCase):
    def test_rear_sump_has_narrow_neck_balanced_shoulders_and_inset_bung_side(self):
        p = json.loads((ROOT / "dimensions.json").read_text(encoding="utf-8"))
        parts, _, _ = make_parts(p)
        pan = parts[0][1].val().Solids()[0]
        start = p["length_mm"] / 2 - p["rear_well_length_mm"] - 5
        end = p["length_mm"] / 2 - 8
        for u, v, inside in [
            (0.08, 0.15, False), (0.08, 0.82, False),
            (0.08, 0.50, True),
            (0.40, 0.05, True), (0.40, 0.85, True),
            (0.40, 0.02, False), (0.40, 0.88, False),
            (0.98, 0.07, True), (0.98, 0.87, True),
            (0.84, 0.95, False), (0.98, 0.97, False),
            (1.02, 0.50, False),
        ]:
            with self.subTest(u=u, v=v):
                x, y = start + u * (end - start), (0.5 - v) * p["rear_sump_width_mm"]
                z = flange_z_at_level(-p["rear_depth_mm"] + p["wall_mm"] / 2, y, p)
                self.assertEqual(pan.isInside(cq.Vector(*floor_frame((x, y, z), p)), 1e-6), inside)
                if inside:
                    cavity_z = flange_z_at_level(-p["rear_depth_mm"] + p["wall_mm"] + 0.1, y, p)
                    self.assertFalse(pan.isInside(cq.Vector(*floor_frame((x, y, cavity_z), p)), 1e-6))
        drain_x = start + 0.84 * (end - start)
        drain_y = -0.4 * p["rear_sump_width_mm"]
        drain_z = flange_z_at_level(-p["rear_depth_mm"] + 21, drain_y, p)
        for dx, inside in [(0, False), (10, True)]:
            point = floor_frame((drain_x + dx, drain_y - 6, drain_z), p)
            self.assertEqual(pan.isInside(cq.Vector(*point), 1e-6), inside)
        rear_plug = next(part for name, part, _ in parts if name == "rear_drain_plug")
        inverse_plug = rear_plug.translate((0, 0, -p["front_depth_mm"])).rotate(
            (0, 0, 0), (1, 0, 0), -p["engine_roll_deg"]
        )
        self.assertAlmostEqual(inverse_plug.val().BoundingBox().ymin, drain_y - 18, places=5)

    def test_roll_changes_flange_angle_without_tilting_floors_or_distorting_holes(self):
        base = json.loads((ROOT / "dimensions.json").read_text(encoding="utf-8"))
        for roll in (15, 0, -15):
            with self.subTest(roll=roll):
                p = dict(base, engine_roll_deg=roll)
                parts, holes, _ = make_parts(p)
                pan = parts[0][1]
                report = validate_floor_geometry(pan, p, len(holes))
                self.assertAlmostEqual(report["measured_flange_to_floor_deg"], abs(roll))
                self.assertAlmostEqual(report["measured_signed_roll_deg"], roll)
                self.assertTrue(all(validate_features(pan, p, holes).values()))
                self.assertEqual(len(holes), 16)
                for name, part, _ in parts:
                    self.assertTrue(part.val().isValid(), name)
                    self.assertEqual(len(part.val().Solids()), 1, name)
                    self.assertGreaterEqual(part.val().BoundingBox().zmin, -1e-6, name)
                    if "estimated" in name:
                        self.assertLess(part.intersect(pan).val().Volume(), 1e-5, name)
                solid = pan.val().Solids()[0]
                for x, depth in [(-150, p["front_depth_mm"]), (147, p["rear_depth_mm"]),
                                 (0, p["bridge_depth_mm"])]:
                    for y in (-60, 60):
                        for level, expected in [
                            (-depth - 0.1, False), (-depth + p["wall_mm"] / 2, True),
                            (-depth + p["wall_mm"] + 0.1, False),
                        ]:
                            point = floor_frame((x, y, flange_z_at_level(level, y, p)), p)
                            self.assertEqual(solid.isInside(cq.Vector(*point), 1e-6), expected)

    def test_rejects_angle_that_breaks_shallow_bridge(self):
        p = json.loads((ROOT / "dimensions.json").read_text(encoding="utf-8"))
        for roll in (30, float("nan")):
            with self.subTest(roll=roll):
                with self.assertRaisesRegex(ValueError, "topology"):
                    make_parts(dict(p, engine_roll_deg=roll))


if __name__ == "__main__":
    unittest.main()
