"""Correction boundary for the raw OCR baseline.

The baseline deliberately ships no corrector.  This module provides only the
typed contract so a later, separately evaluated correction experiment cannot
overwrite raw OCR observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CorrectionResult:
    status: str = "skipped"
    corrected_text: str | None = None
    method: str | None = None
    changes: list[dict[str, object]] = field(default_factory=list)


class Corrector(Protocol):
    """Future correction implementations must return an auditable result."""

    def correct(self, raw_text: str) -> CorrectionResult: ...


def skipped_correction() -> CorrectionResult:
    """Return the only correction result used by the baseline."""

    return CorrectionResult()
