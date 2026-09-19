from __future__ import annotations

import unittest

from handwritten_ocr.correction import skipped_correction
from handwritten_ocr.results import DocumentResult, EvaluationRecord, RegionResult, to_data


class ResultTests(unittest.TestCase):
    def test_raw_text_and_skipped_correction_are_preserved(self) -> None:
        raw = "Raw OCR Name:"
        region = RegionResult(
            region_id="line-0000",
            detector_index=3,
            sorted_index=0,
            raw_polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            sorted_polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            detector_score=None,
            crop_path=None,
            crop_provenance={},
            raw_text=raw,
            recognition_score=None,
            recognition_order=0,
            correction=skipped_correction(),
        )
        document = DocumentResult(
            document_id="document",
            source_image="source.png",
            source_path="source.png",
            source_image_sha256="abc",
            image_metadata={},
            pipeline_metadata={},
            regions=[region],
            document_text_raw=raw,
            document_text_corrected=None,
            evaluation=EvaluationRecord(False, "ground_truth_unavailable"),
            timing={},
        )
        payload = to_data(document)
        self.assertEqual(payload["document_text_raw"], raw)
        self.assertEqual(payload["regions"][0]["correction"]["status"], "skipped")
        self.assertEqual(payload["regions"][0]["correction"]["changes"], [])
