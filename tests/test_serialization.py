from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from handwritten_ocr.correction import skipped_correction
from handwritten_ocr.results import DocumentResult, EvaluationRecord, RegionResult, to_data
from handwritten_ocr.serialization import (
    configuration_fingerprint,
    new_run_directory,
    validate_payload,
    write_document_artifacts,
    write_run_manifest,
)


def make_document() -> DocumentResult:
    region = RegionResult(
        region_id="line-0000",
        detector_index=0,
        sorted_index=0,
        raw_polygon=[[1.0, 1.0], [5.0, 1.0], [5.0, 3.0], [1.0, 3.0]],
        sorted_polygon=[[1.0, 1.0], [5.0, 1.0], [5.0, 3.0], [1.0, 3.0]],
        detector_score=None,
        crop_path=None,
        crop_provenance={},
        raw_text="raw",
        recognition_score=0.5,
        recognition_order=0,
        correction=skipped_correction(),
    )
    return DocumentResult(
        document_id="doc",
        source_image="source.png",
        source_path="source.png",
        source_image_sha256="a" * 64,
        image_metadata={},
        pipeline_metadata={},
        regions=[region],
        document_text_raw="raw",
        document_text_corrected=None,
        evaluation=EvaluationRecord(False, "ground_truth_unavailable"),
        timing={"serialization_ms": None},
    )


class SerializationTests(unittest.TestCase):
    def test_schema_and_artifacts_accept_null_runtime_facts(self) -> None:
        document = make_document()
        validate_payload(to_data(document))
        with tempfile.TemporaryDirectory() as directory:
            run_id, run_directory, timestamp = new_run_directory(directory, "b" * 64)
            target = write_document_artifacts(
                run_directory,
                document,
                np.full((10, 10, 3), 255, dtype=np.uint8),
                {"line-0000": np.full((3, 5, 3), 127, dtype=np.uint8)},
            )
            self.assertTrue((target / "document.json").exists())
            self.assertTrue((target / "raw.txt").exists())
            manifest = {
                "run_id": run_id,
                "created_at_utc": timestamp,
                "config_sha256": "b" * 64,
                "runtime": {"pipeline_engine": None, "resolved_detector_engine": None},
                "documents": [],
                "integration_status": "test",
            }
            manifest_path = write_run_manifest(run_directory, manifest)
            self.assertTrue(manifest_path.exists())

    def test_configuration_fingerprint_is_deterministic(self) -> None:
        self.assertEqual(configuration_fingerprint({"b": 2, "a": 1}), configuration_fingerprint({"a": 1, "b": 2}))
