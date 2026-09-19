from __future__ import annotations

import unittest

from handwritten_ocr.adapter import PaddleXCompatibilityError, restore_recognition_order
from handwritten_ocr.geometry import PolygonError, map_sorted_to_detector_indices


class MappingTests(unittest.TestCase):
    def test_detector_to_sorted_mapping_is_geometry_based(self) -> None:
        first = [[0, 0], [4, 0], [4, 1], [0, 1]]
        second = [[0, 5], [4, 5], [4, 6], [0, 6]]
        self.assertEqual(map_sorted_to_detector_indices([first, second], [second, first]), [1, 0])

    def test_unknown_sorted_polygon_fails_closed(self) -> None:
        first = [[0, 0], [4, 0], [4, 1], [0, 1]]
        unknown = [[0, 5], [4, 5], [4, 6], [0, 6]]
        with self.assertRaises(PolygonError):
            map_sorted_to_detector_indices([first], [unknown])

    def test_recognition_results_restore_by_crop_identity(self) -> None:
        restored = restore_recognition_order(
            batch_sorted_positions=[7, 4],
            recognition_results=[("wide", 0.8), ("narrow", 0.9)],
            expected_positions=[4, 7],
        )
        self.assertEqual(restored[7], ("wide", 0.8, 0))
        self.assertEqual(restored[4], ("narrow", 0.9, 1))

    def test_bad_recognition_identity_fails_closed(self) -> None:
        with self.assertRaises(PaddleXCompatibilityError):
            restore_recognition_order([0, 0], [("a", 1.0), ("b", 1.0)], expected_positions=[0, 1])
