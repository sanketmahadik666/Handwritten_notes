"""Loading and validation for the requested (not resolved) OCR configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a requested configuration is invalid or unsupported."""


@dataclass(frozen=True)
class RuntimeConfig:
    paddleocr_version: str
    paddlex_version: str
    paddlepaddle_version: str
    requested_engine: str | None
    device: str | None
    enable_mkldnn: bool
    enable_cinn: bool
    cpu_threads: int


@dataclass(frozen=True)
class PipelineConfig:
    lang: str
    ocr_version: str | None
    use_doc_orientation_classify: bool
    use_doc_unwarping: bool
    use_textline_orientation: bool
    text_rec_score_thresh: float


@dataclass(frozen=True)
class DetectorConfig:
    model_name: str
    model_dir: str | None
    limit_side_len: int
    limit_type: str
    max_side_limit: int
    thresh: float
    box_thresh: float
    unclip_ratio: float


@dataclass(frozen=True)
class ModelConfig:
    model_name: str
    model_dir: str | None


@dataclass(frozen=True)
class PreprocessingConfig:
    mode: str
    operations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class AppConfig:
    database_path: str
    ocr_worker_concurrency: int
    notes_worker_concurrency: int
    max_retries: int
    queue_poll_interval_seconds: int


@dataclass(frozen=True)
class EvaluationConfig:
    unicode_normalization: str
    case_sensitive: bool
    whitespace: str
    punctuation: str


@dataclass(frozen=True)
class RunConfig:
    runtime: RuntimeConfig
    pipeline: PipelineConfig
    detector: DetectorConfig
    recognizer: ModelConfig
    document_preprocessing: dict[str, bool]
    model_preprocessing: dict[str, str]
    preprocessing: PreprocessingConfig
    evaluation: EvaluationConfig
    correction_status: str
    app: AppConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["preprocessing"]["operations"] = list(value["preprocessing"]["operations"])
        if value.get("app") is None:
            value.pop("app", None)
        return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ConfigError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _required(mapping: dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"{label}.{key} is required")
    return mapping[key]


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be a boolean")
    return value


def load_config(path: str | Path) -> RunConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    root = _mapping(raw, "configuration")
    _reject_unknown(
        root,
        {
            "runtime",
            "pipeline",
            "models",
            "document_preprocessing",
            "model_preprocessing",
            "preprocessing",
            "evaluation",
            "correction",
            "app",
        },
        "configuration",
    )
    runtime_raw = _mapping(_required(root, "runtime", "configuration"), "runtime")
    _reject_unknown(
        runtime_raw,
        {
            "paddleocr_version",
            "paddlex_version",
            "paddlepaddle_version",
            "requested_engine",
            "device",
            "enable_mkldnn",
            "enable_cinn",
            "cpu_threads",
        },
        "runtime",
    )
    pipeline_raw = _mapping(_required(root, "pipeline", "configuration"), "pipeline")
    _reject_unknown(
        pipeline_raw,
        {
            "lang",
            "ocr_version",
            "use_doc_orientation_classify",
            "use_doc_unwarping",
            "use_textline_orientation",
            "text_rec_score_thresh",
        },
        "pipeline",
    )
    models_raw = _mapping(_required(root, "models", "configuration"), "models")
    _reject_unknown(models_raw, {"detector", "recognizer"}, "models")
    detector_raw = _mapping(_required(models_raw, "detector", "models"), "models.detector")
    _reject_unknown(
        detector_raw,
        {
            "model_name",
            "model_dir",
            "limit_side_len",
            "limit_type",
            "max_side_limit",
            "thresh",
            "box_thresh",
            "unclip_ratio",
        },
        "models.detector",
    )
    recognizer_raw = _mapping(_required(models_raw, "recognizer", "models"), "models.recognizer")
    _reject_unknown(recognizer_raw, {"model_name", "model_dir"}, "models.recognizer")
    document_raw = _mapping(
        _required(root, "document_preprocessing", "configuration"), "document_preprocessing"
    )
    _reject_unknown(
        document_raw,
        {"orientation_classification", "unwarping", "textline_orientation"},
        "document_preprocessing",
    )
    model_pre_raw = _mapping(
        _required(root, "model_preprocessing", "configuration"), "model_preprocessing"
    )
    _reject_unknown(model_pre_raw, {"detector", "recognizer"}, "model_preprocessing")
    preprocessing_raw = _mapping(_required(root, "preprocessing", "configuration"), "preprocessing")
    _reject_unknown(preprocessing_raw, {"mode", "operations"}, "preprocessing")
    evaluation_raw = _mapping(_required(root, "evaluation", "configuration"), "evaluation")
    _reject_unknown(
        evaluation_raw,
        {"unicode_normalization", "case_sensitive", "whitespace", "punctuation"},
        "evaluation",
    )
    correction_raw = _mapping(_required(root, "correction", "configuration"), "correction")
    _reject_unknown(correction_raw, {"status"}, "correction")

    app_raw = None
    if "app" in root:
        app_raw = _mapping(root["app"], "app")
        _reject_unknown(
            app_raw,
            {
                "database_path",
                "ocr_worker_concurrency",
                "notes_worker_concurrency",
                "max_retries",
                "queue_poll_interval_seconds",
            },
            "app",
        )
        app_config = AppConfig(
            database_path=str(_required(app_raw, "database_path", "app")),
            ocr_worker_concurrency=int(app_raw.get("ocr_worker_concurrency", 1)),
            notes_worker_concurrency=int(app_raw.get("notes_worker_concurrency", 2)),
            max_retries=int(app_raw.get("max_retries", 3)),
            queue_poll_interval_seconds=int(app_raw.get("queue_poll_interval_seconds", 5)),
        )
    else:
        app_config = AppConfig(
            database_path=".local/jobs.sqlite3",
            ocr_worker_concurrency=1,
            notes_worker_concurrency=2,
            max_retries=3,
            queue_poll_interval_seconds=5,
        )

    operations = _required(preprocessing_raw, "operations", "preprocessing")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ConfigError("preprocessing.operations must be a list of mappings")

    config = RunConfig(
        runtime=RuntimeConfig(
            paddleocr_version=str(_required(runtime_raw, "paddleocr_version", "runtime")),
            paddlex_version=str(_required(runtime_raw, "paddlex_version", "runtime")),
            paddlepaddle_version=str(_required(runtime_raw, "paddlepaddle_version", "runtime")),
            requested_engine=_required(runtime_raw, "requested_engine", "runtime"),
            device=runtime_raw.get("device"),
            enable_mkldnn=_bool(_required(runtime_raw, "enable_mkldnn", "runtime"), "runtime.enable_mkldnn"),
            enable_cinn=_bool(_required(runtime_raw, "enable_cinn", "runtime"), "runtime.enable_cinn"),
            cpu_threads=int(_required(runtime_raw, "cpu_threads", "runtime")),
        ),
        pipeline=PipelineConfig(
            lang=str(_required(pipeline_raw, "lang", "pipeline")),
            ocr_version=pipeline_raw.get("ocr_version"),
            use_doc_orientation_classify=_bool(
                _required(pipeline_raw, "use_doc_orientation_classify", "pipeline"),
                "pipeline.use_doc_orientation_classify",
            ),
            use_doc_unwarping=_bool(
                _required(pipeline_raw, "use_doc_unwarping", "pipeline"),
                "pipeline.use_doc_unwarping",
            ),
            use_textline_orientation=_bool(
                _required(pipeline_raw, "use_textline_orientation", "pipeline"),
                "pipeline.use_textline_orientation",
            ),
            text_rec_score_thresh=float(_required(pipeline_raw, "text_rec_score_thresh", "pipeline")),
        ),
        detector=DetectorConfig(
            model_name=str(_required(detector_raw, "model_name", "models.detector")),
            model_dir=detector_raw.get("model_dir"),
            limit_side_len=int(_required(detector_raw, "limit_side_len", "models.detector")),
            limit_type=str(_required(detector_raw, "limit_type", "models.detector")),
            max_side_limit=int(_required(detector_raw, "max_side_limit", "models.detector")),
            thresh=float(_required(detector_raw, "thresh", "models.detector")),
            box_thresh=float(_required(detector_raw, "box_thresh", "models.detector")),
            unclip_ratio=float(_required(detector_raw, "unclip_ratio", "models.detector")),
        ),
        recognizer=ModelConfig(
            model_name=str(_required(recognizer_raw, "model_name", "models.recognizer")),
            model_dir=recognizer_raw.get("model_dir"),
        ),
        document_preprocessing={
            "orientation_classification": _bool(
                _required(document_raw, "orientation_classification", "document_preprocessing"),
                "document_preprocessing.orientation_classification",
            ),
            "unwarping": _bool(
                _required(document_raw, "unwarping", "document_preprocessing"),
                "document_preprocessing.unwarping",
            ),
            "textline_orientation": _bool(
                _required(document_raw, "textline_orientation", "document_preprocessing"),
                "document_preprocessing.textline_orientation",
            ),
        },
        model_preprocessing={
            "detector": str(_required(model_pre_raw, "detector", "model_preprocessing")),
            "recognizer": str(_required(model_pre_raw, "recognizer", "model_preprocessing")),
        },
        preprocessing=PreprocessingConfig(
            mode=str(_required(preprocessing_raw, "mode", "preprocessing")),
            operations=tuple(operations),
        ),
        evaluation=EvaluationConfig(
            unicode_normalization=str(_required(evaluation_raw, "unicode_normalization", "evaluation")),
            case_sensitive=_bool(_required(evaluation_raw, "case_sensitive", "evaluation"), "evaluation.case_sensitive"),
            whitespace=str(_required(evaluation_raw, "whitespace", "evaluation")),
            punctuation=str(_required(evaluation_raw, "punctuation", "evaluation")),
        ),
        correction_status=str(_required(correction_raw, "status", "correction")),
        app=app_config,
    )
    validate_config(config)
    return config


def validate_config(config: RunConfig) -> None:
    if config.runtime.requested_engine is not None:
        raise ConfigError("runtime.requested_engine must remain null for this baseline")
    if config.runtime.cpu_threads <= 0:
        raise ConfigError("runtime.cpu_threads must be positive")
    if config.detector.model_name != "PP-OCRv6_medium_det":
        raise ConfigError("baseline detector must be PP-OCRv6_medium_det")
    if config.recognizer.model_name != "PP-OCRv6_medium_rec":
        raise ConfigError("baseline recognizer must be PP-OCRv6_medium_rec")
    if config.correction_status != "skipped":
        raise ConfigError("the baseline correction.status must be 'skipped'")
    if config.preprocessing.mode != "original" or config.preprocessing.operations:
        raise ConfigError("document preprocessing experiments are not enabled in the baseline")
    if config.pipeline.use_doc_orientation_classify or config.pipeline.use_doc_unwarping or config.pipeline.use_textline_orientation:
        raise ConfigError("document-level optional processing must be disabled in the baseline")
    expected_document_flags = {
        "orientation_classification": config.pipeline.use_doc_orientation_classify,
        "unwarping": config.pipeline.use_doc_unwarping,
        "textline_orientation": config.pipeline.use_textline_orientation,
    }
    if config.document_preprocessing != expected_document_flags:
        raise ConfigError("document_preprocessing must match the pipeline flags")
    if config.model_preprocessing != {"detector": "PaddleX-managed", "recognizer": "PaddleX-managed"}:
        raise ConfigError("model preprocessing must remain PaddleX-managed")
    if config.evaluation.unicode_normalization != "NFC" or not config.evaluation.case_sensitive:
        raise ConfigError("baseline evaluation must use NFC and remain case-sensitive")
    if config.evaluation.whitespace != "collapse_runs" or config.evaluation.punctuation != "preserve":
        raise ConfigError("baseline evaluation normalization must collapse whitespace and preserve punctuation")
    if config.pipeline.text_rec_score_thresh != 0.0:
        raise ConfigError("baseline text_rec_score_thresh must remain 0.0")
    if config.detector.limit_type != "max":
        raise ConfigError("baseline detector limit_type must be 'max'")
    if config.detector.limit_side_len != 960 or config.detector.max_side_limit != 4000:
        raise ConfigError("baseline detector must use limit_side_len=960 and max_side_limit=4000")
    if not 0.0 <= config.detector.thresh <= 1.0 or not 0.0 <= config.detector.box_thresh <= 1.0:
        raise ConfigError("detector thresh and box_thresh must be in [0, 1]")
    if config.detector.unclip_ratio <= 0:
        raise ConfigError("detector unclip_ratio must be positive")
