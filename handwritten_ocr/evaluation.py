"""Verified-ground-truth evaluation with auditable exclusions and edit counts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Sequence, TypeVar

from .config import EvaluationConfig
from .results import EvaluationRecord, MetricResult


class GroundTruthError(ValueError):
    """Raised for malformed ground-truth provenance manifests."""


@dataclass(frozen=True)
class GroundTruthEntry:
    source_image: str
    verified: bool
    reference_text: str
    exclusion: dict[str, Any]


def load_ground_truth(path: str | Path) -> dict[str, GroundTruthEntry]:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GroundTruthError(f"Unable to read ground-truth manifest {manifest_path}: {exc}") from exc
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        raise GroundTruthError("ground-truth manifest requires a documents list")
    entries: dict[str, GroundTruthEntry] = {}
    for item in documents:
        if not isinstance(item, dict):
            raise GroundTruthError("each ground-truth document must be a mapping")
        source_image = item.get("source_image")
        reference_text = item.get("reference_text")
        if not isinstance(source_image, str) or not isinstance(reference_text, str):
            raise GroundTruthError("ground-truth documents require source_image and reference_text strings")
        if source_image in entries:
            raise GroundTruthError(f"duplicate ground-truth entry for {source_image}")
        entries[source_image] = GroundTruthEntry(
            source_image=source_image,
            verified=item.get("verified") is True,
            reference_text=reference_text,
            exclusion=item.get("exclusion") if isinstance(item.get("exclusion"), dict) else {},
        )
    return entries


def normalize_text(text: str, config: EvaluationConfig) -> str:
    value = unicodedata.normalize(config.unicode_normalization, text)
    if not config.case_sensitive:
        value = value.casefold()
    if config.whitespace == "collapse_runs":
        value = re.sub(r"\s+", " ", value).strip()
    else:
        raise GroundTruthError(f"unsupported whitespace normalization: {config.whitespace}")
    if config.punctuation != "preserve":
        raise GroundTruthError(f"unsupported punctuation normalization: {config.punctuation}")
    return value


def apply_exclusion(raw_text: str, exclusion: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Apply a manifest-declared trailing-line exclusion without changing raw OCR."""

    recorded = dict(exclusion)
    expected = exclusion.get("exclude_trailing_raw_lines", [])
    if exclusion.get("status") != "applied" or not expected:
        recorded.setdefault("status", "not_requested")
        return raw_text, recorded
    if not isinstance(expected, list) or not all(isinstance(line, str) for line in expected):
        raise GroundTruthError("exclusion.exclude_trailing_raw_lines must be a list of strings")
    lines = raw_text.splitlines()
    if len(lines) < len(expected) or lines[-len(expected) :] != expected:
        recorded["status"] = "not_applied"
        recorded["observed_trailing_lines"] = lines[-len(expected) :] if expected else []
        return raw_text, recorded
    recorded["status"] = "applied"
    recorded["excluded_raw_lines"] = expected
    return "\n".join(lines[: -len(expected)]), recorded


T = TypeVar("T")


def _metric(reference: Sequence[T], hypothesis: Sequence[T]) -> MetricResult:
    """Levenshtein alignment with deterministic S/I/D provenance."""

    # Cells are total edits, substitutions, insertions, deletions.  Tuple order
    # keeps ties deterministic while total_edits remains the primary metric.
    cells: list[list[tuple[int, int, int, int]]] = [
        [(0, 0, 0, 0) for _ in range(len(hypothesis) + 1)] for _ in range(len(reference) + 1)
    ]
    for index in range(1, len(reference) + 1):
        cells[index][0] = (index, 0, 0, index)
    for index in range(1, len(hypothesis) + 1):
        cells[0][index] = (index, 0, index, 0)
    for ref_index in range(1, len(reference) + 1):
        for hyp_index in range(1, len(hypothesis) + 1):
            if reference[ref_index - 1] == hypothesis[hyp_index - 1]:
                cells[ref_index][hyp_index] = cells[ref_index - 1][hyp_index - 1]
                continue
            diagonal = cells[ref_index - 1][hyp_index - 1]
            deletion = cells[ref_index - 1][hyp_index]
            insertion = cells[ref_index][hyp_index - 1]
            candidates = (
                (diagonal[0] + 1, diagonal[1] + 1, diagonal[2], diagonal[3]),
                (deletion[0] + 1, deletion[1], deletion[2], deletion[3] + 1),
                (insertion[0] + 1, insertion[1], insertion[2] + 1, insertion[3]),
            )
            cells[ref_index][hyp_index] = min(candidates)
    total, substitutions, insertions, deletions = cells[-1][-1]
    return MetricResult(
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        total_edits=total,
        reference_length=len(reference),
        hypothesis_length=len(hypothesis),
        rate=(total / len(reference)) if reference else None,
    )


def evaluate_raw_text(
    source_image: str,
    raw_text: str,
    entries: dict[str, GroundTruthEntry] | None,
    config: EvaluationConfig,
) -> EvaluationRecord:
    entry = entries.get(source_image) if entries is not None else None
    if entry is None:
        return EvaluationRecord(ground_truth_available=False, status="ground_truth_unavailable")
    if not entry.verified:
        return EvaluationRecord(ground_truth_available=False, status="ground_truth_unverified")
    evaluation_hypothesis, exclusion = apply_exclusion(raw_text, entry.exclusion)
    normalized_reference = normalize_text(entry.reference_text, config)
    normalized_hypothesis = normalize_text(evaluation_hypothesis, config)
    character = _metric(list(normalized_reference), list(normalized_hypothesis))
    word = _metric(normalized_reference.split(), normalized_hypothesis.split())
    status = "evaluated" if normalized_reference else "unavailable_empty_reference"
    return EvaluationRecord(
        ground_truth_available=bool(normalized_reference),
        status=status,
        reference_text=entry.reference_text,
        evaluation_hypothesis_text=evaluation_hypothesis,
        normalized_reference_text=normalized_reference,
        normalized_hypothesis_text=normalized_hypothesis,
        exclusion=exclusion,
        character=character,
        word=word,
    )


def aggregate_evaluations(records: Sequence[EvaluationRecord]) -> dict[str, Any]:
    """Micro-aggregate edit counts; do not average document-level rates."""

    def aggregate(metric_name: str) -> dict[str, Any] | None:
        metrics = [getattr(record, metric_name) for record in records]
        usable = [metric for metric in metrics if metric is not None and metric.reference_length > 0]
        if not usable:
            return None
        substitutions = sum(metric.substitutions for metric in usable)
        insertions = sum(metric.insertions for metric in usable)
        deletions = sum(metric.deletions for metric in usable)
        total = sum(metric.total_edits for metric in usable)
        denominator = sum(metric.reference_length for metric in usable)
        return {
            "substitutions": substitutions,
            "insertions": insertions,
            "deletions": deletions,
            "total_edits": total,
            "reference_length": denominator,
            "rate": total / denominator,
            "aggregation": "micro_total_edits_over_total_reference_length",
        }

    return {"character": aggregate("character"), "word": aggregate("word")}
