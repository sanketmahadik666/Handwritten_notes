from __future__ import annotations

import unittest

from handwritten_ocr.geometry import PolygonError, invert_homography, require_restorable_geometry, transform_polygon


class GeometryTests(unittest.TestCase):
    def test_invertible_transform_round_trip(self) -> None:
        polygon = [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]
        matrix = [[2.0, 0.0, 10.0], [0.0, 2.0, 5.0], [0.0, 0.0, 1.0]]
        transformed = transform_polygon(polygon, matrix)
        restored = transform_polygon(transformed, invert_homography(matrix))
        for expected, actual in zip(polygon, restored):
            self.assertAlmostEqual(expected[0], actual[0])
            self.assertAlmostEqual(expected[1], actual[1])

    def test_non_restorable_geometry_is_rejected(self) -> None:
        with self.assertRaises(PolygonError):
            require_restorable_geometry({"geometric": True})
        with self.assertRaises(PolygonError):
            require_restorable_geometry({"geometric": True, "matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]]})
