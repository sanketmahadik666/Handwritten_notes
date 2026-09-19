from __future__ import annotations

import unittest

from handwritten_ocr.config import EvaluationConfig
from handwritten_ocr.evaluation import GroundTruthEntry, aggregate_evaluations, evaluate_raw_text


EVALUATION_CONFIG = EvaluationConfig("NFC", True, "collapse_runs", "preserve")


class EvaluationTests(unittest.TestCase):
    def test_explicit_name_exclusion_does_not_mutate_raw_text(self) -> None:
        raw = "Hello\nName:"
        entry = GroundTruthEntry(
            "page.png",
            True,
            "Hello",
            {
                "status": "applied",
                "reason": "printed trailing Name field excluded",
                "source": "manual_ground_truth_annotation",
                "exclude_trailing_raw_lines": ["Name:"],
            },
        )
        record = evaluate_raw_text("page.png", raw, {"page.png": entry}, EVALUATION_CONFIG)
        self.assertEqual(raw, "Hello\nName:")
        self.assertEqual(record.evaluation_hypothesis_text, "Hello")
        self.assertEqual(record.exclusion["status"], "applied")
        self.assertEqual(record.character.rate, 0.0)
        self.assertEqual(record.word.rate, 0.0)

    def test_empty_reference_has_no_rate(self) -> None:
        entry = GroundTruthEntry("empty.png", True, "", {})
        record = evaluate_raw_text("empty.png", "nonempty", {"empty.png": entry}, EVALUATION_CONFIG)
        self.assertEqual(record.status, "unavailable_empty_reference")
        self.assertIsNone(record.character.rate)
        self.assertIsNone(record.word.rate)

    def test_micro_aggregate_uses_total_edits(self) -> None:
        entries = {
            "one.png": GroundTruthEntry("one.png", True, "abc", {}),
            "two.png": GroundTruthEntry("two.png", True, "a", {}),
        }
        records = [
            evaluate_raw_text("one.png", "axc", entries, EVALUATION_CONFIG),
            evaluate_raw_text("two.png", "", entries, EVALUATION_CONFIG),
        ]
        aggregate = aggregate_evaluations(records)
        self.assertEqual(aggregate["character"]["total_edits"], 2)
        self.assertEqual(aggregate["character"]["reference_length"], 4)
        self.assertEqual(aggregate["character"]["rate"], 0.5)
