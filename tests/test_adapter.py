from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from handwritten_ocr.adapter import PaddleX37Adapter, PaddleXCompatibilityError
from handwritten_ocr.config import load_config


ROOT = Path(__file__).resolve().parent.parent


class _FakePipeline:
    def get_text_det_params(self, *args: object) -> dict[str, object]:
        return {"thresh": 0.3}

    def _sort_boxes(self, polygons: np.ndarray) -> list[np.ndarray]:
        return list(reversed(list(polygons)))

    def _crop_by_polys(self, _image: np.ndarray, polygons: np.ndarray) -> list[np.ndarray]:
        crops = []
        for index, _polygon in enumerate(polygons):
            height = 8 + index
            width = 24 - index * 4
            crops.append(np.full((height, width, 3), 90, dtype=np.uint8))
        return crops


class AdapterProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(ROOT / "config" / "baseline.yaml")
        self.adapter = PaddleX37Adapter(self.config)
        self.adapter._pipeline = _FakePipeline()
        self.image = np.full((32, 48, 3), 255, dtype=np.uint8)
        self.wide = [[0.0, 0.0], [20.0, 0.0], [20.0, 4.0], [0.0, 4.0]]
        self.narrow = [[0.0, 10.0], [6.0, 10.0], [6.0, 18.0], [0.0, 18.0]]

    def test_mismatched_detector_scores_fail_closed(self) -> None:
        self.adapter._detector = lambda _images, **_kwargs: [{"dt_polys": [self.wide, self.narrow], "dt_scores": [0.9]}]
        self.adapter._recognizer = lambda _crops, **_kwargs: []
        with self.assertRaises(PaddleXCompatibilityError):
            self.adapter.process(self.image)

    def test_recognition_is_restored_by_crop_identity(self) -> None:
        self.adapter._detector = lambda _images, **_kwargs: [
            {"dt_polys": [self.wide, self.narrow], "dt_scores": [0.4, 0.8]}
        ]

        def recognizer(crops: list[np.ndarray], **_kwargs: object) -> list[dict[str, object]]:
            return [{"rec_text": f"crop-{crop.shape[1]}", "rec_score": 0.5 + (0.1 * index)} for index, crop in enumerate(crops)]

        self.adapter._recognizer = recognizer
        output = self.adapter.process(self.image)
        ordered = [region for region in output.regions if region.sorted_index is not None]
        self.assertEqual([region.detector_index for region in ordered], [1, 0])
        texts = {region.detector_index: region.raw_text for region in ordered}
        self.assertEqual(texts[1], "crop-24")
        self.assertEqual(texts[0], "crop-20")
        self.assertEqual(ordered[0].detector_score, 0.8)
        self.assertEqual(ordered[0].raw_polygon, self.narrow)
