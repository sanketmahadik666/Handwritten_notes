"""Read-only runtime and compatibility doctor command."""

from __future__ import annotations

from typing import Any

from .adapter import PaddleX37Adapter
from .config import RunConfig
from .runtime import installed_versions


def doctor_report(config: RunConfig) -> dict[str, Any]:
    adapter = PaddleX37Adapter(config)
    observation = adapter.runtime_observation()
    versions = installed_versions()
    unavailable = [
        name
        for name in ("pipeline_engine", "resolved_detector_engine", "resolved_recognizer_engine")
        if observation.get(name) is None
    ]
    return {
        "status": "compatible",
        "configured": {
            "requested_engine": config.runtime.requested_engine,
            "document_preprocessing": config.document_preprocessing,
            "models": {"detector": config.detector.model_name, "recognizer": config.recognizer.model_name},
        },
        "observed": observation,
        "dependencies": versions,
        "unavailable": unavailable,
    }
