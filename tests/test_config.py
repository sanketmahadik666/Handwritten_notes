from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from handwritten_ocr.config import ConfigError, load_config
from handwritten_ocr.runtime import RuntimeValidationError, validate_runtime_versions


ROOT = Path(__file__).resolve().parent.parent


class ConfigTests(unittest.TestCase):
    def test_baseline_loads_with_null_requested_engine(self) -> None:
        config = load_config(ROOT / "config" / "baseline.yaml")
        self.assertIsNone(config.runtime.requested_engine)
        self.assertEqual(config.preprocessing.operations, ())
        self.assertEqual(config.model_preprocessing["detector"], "PaddleX-managed")
        self.assertEqual(config.detector.limit_side_len, 960)
        self.assertEqual(config.detector.limit_type, "max")
        self.assertEqual(config.detector.unclip_ratio, 1.5)

    def test_non_null_engine_is_rejected(self) -> None:
        content = (ROOT / "config" / "baseline.yaml").read_text(encoding="utf-8").replace("requested_engine: null", "requested_engine: paddle_static")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_runtime_version_validation_accepts_exact_values(self) -> None:
        config = load_config(ROOT / "config" / "baseline.yaml")
        observed = validate_runtime_versions(
            config,
            {
                "python": "3.12.10",
                "paddleocr": "3.7.0",
                "paddlex": "3.7.2",
                "paddlepaddle": "3.3.1",
                "numpy": "2.3.5",
                "opencv": "4.10.0",
                "omp_num_threads": "1",
            },
        )
        self.assertEqual(observed["paddlex"], "3.7.2")

    def test_runtime_version_validation_rejects_mismatch(self) -> None:
        config = load_config(ROOT / "config" / "baseline.yaml")
        with self.assertRaises(RuntimeValidationError):
            validate_runtime_versions(
                config,
                {
                    "python": "3.12.10",
                    "paddleocr": "3.7.0",
                    "paddlex": "9.9.9",
                    "paddlepaddle": "3.3.1",
                    "numpy": "2.3.5",
                    "opencv": "4.10.0",
                    "omp_num_threads": "1",
                },
            )

    def test_unknown_configuration_fields_are_rejected(self) -> None:
        content = (ROOT / "config" / "baseline.yaml").read_text(encoding="utf-8") + "\nextra_section: true\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_runtime_rejects_non_pinned_python(self) -> None:
        config = load_config(ROOT / "config" / "baseline.yaml")
        with self.assertRaises(RuntimeValidationError):
            validate_runtime_versions(
                config,
                {
                    "python": "3.11.0",
                    "paddleocr": "3.7.0",
                    "paddlex": "3.7.2",
                    "paddlepaddle": "3.3.1",
                    "numpy": "2.3.5",
                    "opencv": "4.10.0",
                    "omp_num_threads": "1",
                },
            )
