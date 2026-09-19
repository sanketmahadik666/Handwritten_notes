"""Version-gated adapter over PaddleOCR/PaddleX 3.7 internal OCR components.

PaddleOCR exposes an OCR pipeline but not the raw detector ordering or cropped
line images needed for an audit trail.  This adapter follows the observed
PaddleX 3.7.2 `_OCRPipeline.predict` flow while checking every private entry
point it depends on.  It deliberately fails closed if that contract changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

import numpy as np

from .config import RunConfig
from .geometry import PolygonError, is_valid_quad, map_sorted_to_detector_indices, polygon_to_list
from .runtime import RuntimeValidationError, validate_runtime_versions


class PaddleXCompatibilityError(RuntimeError):
    """Raised instead of guessing when the checked PaddleX contract changes."""


@dataclass
class AdapterRegion:
    detector_index: int
    sorted_index: int | None
    raw_polygon: list[list[float]]
    sorted_polygon: list[list[float]] | None
    detector_score: float | None
    crop: np.ndarray | None = None
    crop_status: str = "pending"
    raw_text: str | None = None
    recognition_score: float | None = None
    recognition_order: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterDocumentOutput:
    regions: list[AdapterRegion]
    timing: dict[str, float | None]


def _safe_value(value: Any) -> Any:
    """Make observation fields JSON-safe without stringifying unavailable data."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return str(value)


def _model_directory_metadata(model: Any) -> dict[str, Any] | None:
    directory = getattr(model, "_model_dir", getattr(model, "model_dir", None))
    if directory is None:
        return None
    path = Path(directory)
    artifacts = [name for name in ("inference.pdmodel", "inference.pdiparams") if (path / name).exists()]
    return {"directory_name": path.name, "exists": path.exists(), "artifacts": artifacts}


def _field(payload: Any, name: str, default: Any = None) -> Any:
    try:
        return payload[name]
    except (KeyError, TypeError, IndexError, AttributeError):
        return default


def _polygon_or_empty(value: Any) -> list[list[float]]:
    try:
        return polygon_to_list(value)
    except PolygonError:
        return []


def restore_recognition_order(
    batch_sorted_positions: Sequence[int],
    recognition_results: Sequence[tuple[str, float]],
    expected_positions: Sequence[int] | None = None,
) -> dict[int, tuple[str, float, int]]:
    """Restore PaddleX aspect-ratio batch output without using text matching."""

    if len(batch_sorted_positions) != len(recognition_results):
        raise PaddleXCompatibilityError("recognizer result count does not match crop-identity batch")
    if len(set(batch_sorted_positions)) != len(batch_sorted_positions):
        raise PaddleXCompatibilityError("recognition batch identity contains duplicate crop positions")
    if expected_positions is not None and sorted(batch_sorted_positions) != sorted(expected_positions):
        raise PaddleXCompatibilityError("recognition batch identity is not a permutation of sorted crops")
    restored: dict[int, tuple[str, float, int]] = {}
    for recognition_order, (sorted_position, result) in enumerate(zip(batch_sorted_positions, recognition_results)):
        text, score = result
        restored[int(sorted_position)] = (text, score, recognition_order)
    return restored


class PaddleX37Adapter:
    """Drive exactly the version-gated PaddleX 3.7.2 detector/crop/recognizer route."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self._ocr: Any | None = None
        self._outer_pipeline: Any | None = None
        self._pipeline: Any | None = None
        self._detector: Any | None = None
        self._recognizer: Any | None = None
        self._versions: dict[str, str | None] | None = None

    def initialize(self) -> None:
        if self._pipeline is not None:
            return
        try:
            self._versions = validate_runtime_versions(self.config)
            from paddleocr import PaddleOCR
        except (ImportError, RuntimeValidationError) as exc:
            raise PaddleXCompatibilityError(str(exc)) from exc

        # `engine` is intentionally absent: requested_engine is null and must stay null.
        kwargs: dict[str, Any] = {
            "lang": self.config.pipeline.lang,
            "text_detection_model_name": self.config.detector.model_name,
            "text_recognition_model_name": self.config.recognizer.model_name,
            "use_doc_orientation_classify": self.config.pipeline.use_doc_orientation_classify,
            "use_doc_unwarping": self.config.pipeline.use_doc_unwarping,
            "use_textline_orientation": self.config.pipeline.use_textline_orientation,
            "text_rec_score_thresh": self.config.pipeline.text_rec_score_thresh,
            "enable_mkldnn": self.config.runtime.enable_mkldnn,
            "enable_cinn": self.config.runtime.enable_cinn,
            "cpu_threads": self.config.runtime.cpu_threads,
        }
        if self.config.pipeline.ocr_version is not None:
            kwargs["ocr_version"] = self.config.pipeline.ocr_version
        if self.config.detector.model_dir is not None:
            kwargs["text_detection_model_dir"] = self.config.detector.model_dir
        if self.config.recognizer.model_dir is not None:
            kwargs["text_recognition_model_dir"] = self.config.recognizer.model_dir
        if self.config.runtime.device is not None:
            kwargs["device"] = self.config.runtime.device

        self._ocr = PaddleOCR(**kwargs)
        self._outer_pipeline = getattr(self._ocr, "paddlex_pipeline", None)
        if self._outer_pipeline is None:
            raise PaddleXCompatibilityError(
                "PaddleX 3.7.2 compatibility contract failed: expected PaddleOCR.paddlex_pipeline"
            )
        self._pipeline = getattr(self._outer_pipeline, "_pipeline", None)
        if self._pipeline is None or type(self._pipeline).__name__ != "_OCRPipeline":
            raise PaddleXCompatibilityError(
                "PaddleX 3.7.2 compatibility contract failed: expected paddlex_pipeline._pipeline as _OCRPipeline"
            )
        self._detector = getattr(self._pipeline, "text_det_model", None)
        self._recognizer = getattr(self._pipeline, "text_rec_model", None)
        checks = {
            "text_det_model predictor": self._detector,
            "text_rec_model predictor": self._recognizer,
            "_sort_boxes": getattr(self._pipeline, "_sort_boxes", None),
            "_crop_by_polys": getattr(self._pipeline, "_crop_by_polys", None),
            "get_text_det_params": getattr(self._pipeline, "get_text_det_params", None),
        }
        missing = [name for name, value in checks.items() if value is None or (name.startswith("_") and not callable(value))]
        if missing:
            raise PaddleXCompatibilityError(
                "PaddleX 3.7.2 compatibility contract failed: expected " + ", ".join(missing)
            )

    @property
    def initialized(self) -> bool:
        return self._pipeline is not None

    def runtime_observation(self) -> dict[str, Any]:
        """Collect direct object observations; never infer a resolved engine."""

        self.initialize()
        assert self._outer_pipeline is not None and self._detector is not None and self._recognizer is not None

        def model_observation(model: Any) -> dict[str, Any]:
            runner = getattr(model, "runner", None)
            return {
                "model_name": getattr(model, "model_name", None),
                "predictor_class": type(model).__name__,
                "predictor_module": type(model).__module__,
                "runner_class": type(runner).__name__ if runner is not None else None,
                "runner_module": type(runner).__module__ if runner is not None else None,
                "device": getattr(model, "device", None),
                "resolved_engine": getattr(model, "engine", None),
                "generated_engine_config": _safe_value(getattr(model, "_engine_config", None)),
                "model_directory": _model_directory_metadata(model),
            }

        detector = model_observation(self._detector)
        recognizer = model_observation(self._recognizer)
        return {
            "versions": self._versions,
            "requested_engine": self.config.runtime.requested_engine,
            "pipeline_engine": getattr(self._outer_pipeline, "engine", None),
            "generated_engine_config": _safe_value(getattr(self._outer_pipeline, "engine_config", None)),
            "resolved_detector_engine": detector["resolved_engine"],
            "resolved_recognizer_engine": recognizer["resolved_engine"],
            "detector_predictor_class": detector["predictor_class"],
            "recognizer_predictor_class": recognizer["predictor_class"],
            "detector": detector,
            "recognizer": recognizer,
            "private_contract": {
                "pipeline_class": type(self._pipeline).__name__ if self._pipeline is not None else None,
                "uses_sort_boxes": True,
                "uses_crop_by_polys": True,
                "recognition_batch_identity": "crop_index_after_PaddleX_aspect_ratio_sort",
            },
            "requested_text_det_params": {
                "limit_side_len": self.config.detector.limit_side_len,
                "limit_type": self.config.detector.limit_type,
                "max_side_limit": self.config.detector.max_side_limit,
                "thresh": self.config.detector.thresh,
                "box_thresh": self.config.detector.box_thresh,
                "unclip_ratio": self.config.detector.unclip_ratio,
            },
            "observed_text_det_params": _safe_value(self._detector_parameters()),
        }

    def _detector_parameters(self) -> dict[str, Any]:
        assert self._pipeline is not None
        try:
            return self._pipeline.get_text_det_params(
                self.config.detector.limit_side_len,
                self.config.detector.limit_type,
                self.config.detector.max_side_limit,
                self.config.detector.thresh,
                self.config.detector.box_thresh,
                self.config.detector.unclip_ratio,
            )
        except Exception as exc:  # private-contract boundary
            raise PaddleXCompatibilityError(
                "PaddleX 3.7.2 compatibility contract failed: get_text_det_params rejected baseline defaults"
            ) from exc

    def process(self, bgr_image: np.ndarray) -> AdapterDocumentOutput:
        """Run detector -> PaddleX sorter/cropper -> recognizer on one BGR image."""

        self.initialize()
        assert self._pipeline is not None and self._detector is not None and self._recognizer is not None
        if not isinstance(bgr_image, np.ndarray) or bgr_image.ndim != 3 or bgr_image.shape[2] != 3:
            raise PaddleXCompatibilityError("adapter requires a decoded BGR image with three channels")

        timing: dict[str, float | None] = {"detection_ms": None, "sorting_ms": None, "cropping_ms": None, "recognition_ms": None}
        started = perf_counter()
        try:
            detector_results = list(self._detector([bgr_image], **self._detector_parameters()))
        except Exception as exc:
            raise PaddleXCompatibilityError("PaddleX detector invocation failed") from exc
        timing["detection_ms"] = (perf_counter() - started) * 1000.0
        if len(detector_results) != 1:
            raise PaddleXCompatibilityError("PaddleX detector returned an unexpected result count for one input image")
        polygons = _field(detector_results[0], "dt_polys")
        if polygons is None:
            raise PaddleXCompatibilityError("PaddleX 3.7.2 compatibility contract failed: detector result lacks dt_polys")
        raw_polygons = list(polygons)
        scores_value = _field(detector_results[0], "dt_scores")
        if scores_value is None:
            scores: list[float | None] = [None] * len(raw_polygons)
        else:
            scores = list(scores_value)
            if len(scores) != len(raw_polygons):
                raise PaddleXCompatibilityError(
                    "PaddleX 3.7.2 compatibility contract failed: dt_scores length does not match dt_polys"
                )

        regions: list[AdapterRegion] = []
        valid_polygons: list[Any] = []
        valid_detector_indices: list[int] = []
        for detector_index, polygon in enumerate(raw_polygons):
            score = None if scores[detector_index] is None else float(scores[detector_index])
            raw_polygon = _polygon_or_empty(polygon)
            if not is_valid_quad(polygon):
                regions.append(
                    AdapterRegion(
                        detector_index=detector_index,
                        sorted_index=None,
                        raw_polygon=raw_polygon,
                        sorted_polygon=None,
                        detector_score=score,
                        crop_status="invalid_polygon",
                        metadata={"reason": "detector polygon is not a non-degenerate quadrilateral"},
                    )
                )
                continue
            valid_polygons.append(polygon)
            valid_detector_indices.append(detector_index)

        if not valid_polygons:
            return AdapterDocumentOutput(regions=regions, timing=timing)

        started = perf_counter()
        try:
            sorted_polygons = list(self._pipeline._sort_boxes(np.asarray(valid_polygons)))
            local_mapping = map_sorted_to_detector_indices(valid_polygons, sorted_polygons)
        except (Exception, PolygonError) as exc:
            raise PaddleXCompatibilityError("PaddleX SortQuadBoxes compatibility contract failed") from exc
        timing["sorting_ms"] = (perf_counter() - started) * 1000.0

        sorted_regions: list[AdapterRegion] = []
        for sorted_index, (polygon, local_index) in enumerate(zip(sorted_polygons, local_mapping)):
            detector_index = valid_detector_indices[local_index]
            sorted_regions.append(
                AdapterRegion(
                    detector_index=detector_index,
                    sorted_index=sorted_index,
                    raw_polygon=_polygon_or_empty(raw_polygons[detector_index]),
                    sorted_polygon=polygon_to_list(polygon),
                    detector_score=None if scores[detector_index] is None else float(scores[detector_index]),
                    metadata={"crop_generation_method": "PaddleX _OCRPipeline._crop_by_polys"},
                )
            )

        started = perf_counter()
        try:
            crops = list(self._pipeline._crop_by_polys(bgr_image, np.asarray(sorted_polygons)))
        except Exception as exc:
            raise PaddleXCompatibilityError("PaddleX CropByPolys compatibility contract failed") from exc
        timing["cropping_ms"] = (perf_counter() - started) * 1000.0
        if len(crops) != len(sorted_regions):
            raise PaddleXCompatibilityError("PaddleX CropByPolys returned a crop count inconsistent with sorted polygons")

        recognisable_positions: list[int] = []
        for position, (region, crop) in enumerate(zip(sorted_regions, crops)):
            if not isinstance(crop, np.ndarray) or crop.size == 0 or crop.ndim < 2 or crop.shape[0] == 0 or crop.shape[1] == 0:
                region.crop_status = "invalid_crop"
                region.metadata["reason"] = "PaddleX crop is empty or invalid"
                continue
            region.crop = crop
            region.crop_status = "saved"
            recognisable_positions.append(position)

        if recognisable_positions:
            aspect_ratio_order = sorted(
                recognisable_positions,
                key=lambda position: sorted_regions[position].crop.shape[1] / float(sorted_regions[position].crop.shape[0]),  # type: ignore[union-attr]
            )
            ordered_crops = [sorted_regions[position].crop for position in aspect_ratio_order]
            started = perf_counter()
            try:
                prediction_items = list(self._recognizer(ordered_crops, return_word_box=False))
            except Exception as exc:
                raise PaddleXCompatibilityError("PaddleX recognizer invocation failed") from exc
            timing["recognition_ms"] = (perf_counter() - started) * 1000.0
            recognition_results: list[tuple[str, float]] = []
            for prediction in prediction_items:
                text = _field(prediction, "rec_text")
                score = _field(prediction, "rec_score")
                if not isinstance(text, str) or score is None:
                    raise PaddleXCompatibilityError(
                        "PaddleX 3.7.2 compatibility contract failed: recognizer result lacks rec_text or rec_score"
                    )
                recognition_results.append((text, float(score)))
            restored = restore_recognition_order(
                aspect_ratio_order,
                recognition_results,
                expected_positions=recognisable_positions,
            )
            for position, (text, score, recognition_order) in restored.items():
                region = sorted_regions[position]
                region.raw_text = text
                region.recognition_score = score
                region.recognition_order = recognition_order

        regions.extend(sorted_regions)
        regions.sort(key=lambda region: (region.sorted_index is None, region.sorted_index if region.sorted_index is not None else region.detector_index))
        return AdapterDocumentOutput(regions=regions, timing=timing)
