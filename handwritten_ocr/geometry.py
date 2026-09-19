"""Polygon identity mapping and future transform validation.

This module intentionally does not implement a reading-order sorter or cropper.
Those operations are delegated to PaddleX in the compatibility adapter.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


class PolygonError(ValueError):
    """Raised when a polygon or geometric transform cannot be trusted."""


def polygon_array(polygon: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(polygon, dtype=np.float64)
    if array.shape != (4, 2) or not np.isfinite(array).all():
        raise PolygonError("expected a finite quadrilateral with shape [4, 2]")
    return array


def is_valid_quad(polygon: Sequence[Sequence[float]]) -> bool:
    try:
        array = polygon_array(polygon)
    except PolygonError:
        return False
    x_values = array[:, 0]
    y_values = array[:, 1]
    area = 0.5 * abs(float(np.dot(x_values, np.roll(y_values, -1)) - np.dot(y_values, np.roll(x_values, -1))))
    return area > 0.0


def polygon_to_list(polygon: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in polygon_array(polygon).tolist()]


def map_sorted_to_detector_indices(
    raw_polygons: Sequence[Sequence[Sequence[float]]],
    sorted_polygons: Sequence[Sequence[Sequence[float]]],
) -> list[int]:
    """Map PaddleX sorter output back to raw detector positions by geometry only."""

    raw_arrays = [polygon_array(polygon) for polygon in raw_polygons]
    consumed: set[int] = set()
    mapping: list[int] = []
    for sorted_polygon in sorted_polygons:
        candidate = polygon_array(sorted_polygon)
        match = next(
            (
                index
                for index, raw_polygon in enumerate(raw_arrays)
                if index not in consumed and np.array_equal(raw_polygon, candidate)
            ),
            None,
        )
        if match is None:
            raise PolygonError("PaddleX sorter returned a polygon not present in raw detector output")
        consumed.add(match)
        mapping.append(match)
    return mapping


def invert_homography(matrix: Sequence[Sequence[float]]) -> np.ndarray:
    transform = np.asarray(matrix, dtype=np.float64)
    if transform.shape != (3, 3) or not np.isfinite(transform).all():
        raise PolygonError("geometric transform must be a finite 3x3 matrix")
    if abs(float(np.linalg.det(transform))) < 1e-12:
        raise PolygonError("geometric transform is not invertible")
    return np.linalg.inv(transform)


def transform_polygon(polygon: Sequence[Sequence[float]], matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    points = polygon_array(polygon)
    transform = np.asarray(matrix, dtype=np.float64)
    if transform.shape != (3, 3):
        raise PolygonError("geometric transform must be a 3x3 matrix")
    homogeneous = np.column_stack((points, np.ones(len(points))))
    transformed = homogeneous @ transform.T
    if np.any(np.isclose(transformed[:, 2], 0.0)):
        raise PolygonError("geometric transform maps a polygon point to infinity")
    return [[float(x / w), float(y / w)] for x, y, w in transformed]


def require_restorable_geometry(operation: dict[str, Any]) -> np.ndarray:
    """Validate an opt-in future geometric operation before it can be applied."""

    if operation.get("geometric") is not True:
        raise PolygonError("only explicitly geometric operations require coordinate restoration")
    if "matrix" not in operation:
        raise PolygonError("geometric operation requires an exact source-to-output matrix")
    return invert_homography(operation["matrix"])
