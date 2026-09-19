"""Typed result and provenance models for raw OCR observations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from .correction import CorrectionResult, skipped_correction


@dataclass
class MetricResult:
    substitutions: int
    insertions: int
    deletions: int
    total_edits: int
    reference_length: int
    hypothesis_length: int
    rate: float | None


@dataclass
class EvaluationRecord:
    ground_truth_available: bool
    status: str
    reference_text: str | None = None
    evaluation_hypothesis_text: str | None = None
    normalized_reference_text: str | None = None
    normalized_hypothesis_text: str | None = None
    exclusion: dict[str, Any] = field(default_factory=dict)
    character: MetricResult | None = None
    word: MetricResult | None = None


@dataclass
class RegionResult:
    region_id: str
    detector_index: int
    sorted_index: int | None
    raw_polygon: list[list[float]]
    sorted_polygon: list[list[float]] | None
    detector_score: float | None
    crop_path: str | None
    crop_provenance: dict[str, Any]
    raw_text: str | None
    recognition_score: float | None
    recognition_order: int | None
    correction: CorrectionResult = field(default_factory=skipped_correction)
    timing: dict[str, float | None] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentResult:
    document_id: str
    source_image: str
    source_path: str
    source_image_sha256: str
    image_metadata: dict[str, Any]
    pipeline_metadata: dict[str, Any]
    regions: list[RegionResult]
    document_text_raw: str
    document_text_corrected: str | None
    evaluation: EvaluationRecord
    timing: dict[str, float | None]
    status: str = "success"
    errors: list[str] = field(default_factory=list)


def to_data(value: Any) -> Any:
    """Convert nested domain models to JSON-safe values without altering text."""

    if is_dataclass(value):
        return to_data(asdict(value))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_data(item) for item in value]
    return value
