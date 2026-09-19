"""Read-only runtime inspection helpers."""

from __future__ import annotations

import os
import platform
import sys
from typing import Any

from .config import RunConfig


class RuntimeValidationError(RuntimeError):
    """Raised when the live ML environment differs from the requested baseline."""


PINNED_DEPENDENCIES = {
    "python": "3.12.10",
    "numpy": "2.3.5",
    "opencv": "4.10.0",
    "omp_num_threads": "1",
}


def installed_versions() -> dict[str, str | None]:
    """Read installed versions without initializing an OCR pipeline."""

    try:
        import paddle
        import paddleocr
        import paddlex
        import cv2
        import numpy
    except ImportError as exc:
        raise RuntimeValidationError(f"Required OCR dependency is unavailable: {exc}") from exc
    return {
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "paddleocr": getattr(paddleocr, "__version__", None),
        "paddlex": getattr(paddlex, "__version__", None),
        "paddlepaddle": getattr(paddle, "__version__", None),
        "numpy": getattr(numpy, "__version__", None),
        "opencv": getattr(cv2, "__version__", None),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
    }


def validate_runtime_versions(config: RunConfig, versions: dict[str, Any] | None = None) -> dict[str, str | None]:
    observed = installed_versions() if versions is None else versions
    expected = {
        "python": PINNED_DEPENDENCIES["python"],
        "paddleocr": config.runtime.paddleocr_version,
        "paddlex": config.runtime.paddlex_version,
        "paddlepaddle": config.runtime.paddlepaddle_version,
        "numpy": PINNED_DEPENDENCIES["numpy"],
        "opencv": PINNED_DEPENDENCIES["opencv"],
        "omp_num_threads": PINNED_DEPENDENCIES["omp_num_threads"],
    }
    mismatches = [
        f"{name}: expected {wanted}, observed {observed.get(name)!r}"
        for name, wanted in expected.items()
        if observed.get(name) != wanted
    ]
    if mismatches:
        raise RuntimeValidationError("Pinned runtime validation failed: " + "; ".join(mismatches))
    return observed
