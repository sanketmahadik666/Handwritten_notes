from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from handwritten_ocr.adapter import AdapterDocumentOutput
from handwritten_ocr.cli import _run
from handwritten_ocr.config import load_config


ROOT = Path(__file__).resolve().parent.parent


class _FakeAdapter:
    def __init__(self, _config: object) -> None:
        pass

    def runtime_observation(self) -> dict[str, object]:
        return {
            "versions": {"paddleocr": "3.7.0", "paddlex": "3.7.2", "paddlepaddle": "3.3.1"},
            "detector": {"model_name": "PP-OCRv6_medium_det", "device": "cpu"},
            "recognizer": {"model_name": "PP-OCRv6_medium_rec", "device": "cpu"},
            "requested_engine": None,
        }

    def process(self, _image: np.ndarray) -> AdapterDocumentOutput:
        return AdapterDocumentOutput(
            regions=[],
            timing={"detection_ms": 1.0, "sorting_ms": None, "cropping_ms": None, "recognition_ms": None},
        )


class CliRunTests(unittest.TestCase):
    def test_unreadable_image_does_not_abort_the_run(self) -> None:
        config = load_config(ROOT / "config" / "baseline.yaml")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            output_root = root / "output"
            input_dir.mkdir()
            image = np.full((8, 8, 3), 120, dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(input_dir / "ok.png"), image))
            (input_dir / "broken.png").write_bytes(b"not-an-image")
            with patch("handwritten_ocr.cli.PaddleX37Adapter", _FakeAdapter):
                run_directory = _run(config, str(input_dir), str(output_root), None)
            manifest = json.loads((run_directory / "run_manifest.json").read_text(encoding="utf-8"))
            statuses = {item["source_image"]: item["status"] for item in manifest["documents"]}
            self.assertEqual(statuses["ok.png"], "success")
            self.assertEqual(statuses["broken.png"], "failed")
            self.assertEqual(manifest["integration_status"], "runtime_pipeline_executed_with_document_errors")
