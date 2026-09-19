"""Schema-validated run artifacts: JSON, raw text, crops, and overlays."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import cv2
import numpy as np
import jsonschema

from .hashing import canonical_sha256
from .results import DocumentResult, RegionResult, to_data


class SerializationError(RuntimeError):
    """Raised when an artifact cannot be represented or persisted safely."""


def schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "run_result.schema.json"


def validate_payload(payload: dict[str, Any]) -> None:
    try:
        schema = json.loads(schema_path().read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(payload)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError, jsonschema.SchemaError) as exc:
        raise SerializationError(f"JSON schema validation failed: {exc}") from exc


def new_run_directory(output_root: str | Path, config_sha256: str) -> tuple[str, Path, str]:
    root = Path(output_root)
    timestamp = datetime.now(timezone.utc)
    base_id = f"run-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{config_sha256[:12]}"
    candidate = root / base_id
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base_id}-{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate.name, candidate, timestamp.isoformat().replace("+00:00", "Z")


def document_id(source_image: str, source_sha256: str) -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(source_image).stem).strip("-") or "document"
    return f"{safe_stem}-{source_sha256[:12]}"


def _write_overlay(path: Path, source_bgr: np.ndarray, regions: list[RegionResult]) -> None:
    overlay = source_bgr.copy()
    for region in regions:
        if region.sorted_polygon is None or len(region.sorted_polygon) != 4:
            continue
        polygon = np.asarray(region.sorted_polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [polygon], True, (0, 200, 0), 2, lineType=cv2.LINE_AA)
        top_left = tuple(np.asarray(region.sorted_polygon[0], dtype=np.int32).tolist())
        label = f"{region.region_id} s={region.sorted_index}"
        cv2.putText(overlay, label, top_left, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), overlay):
        raise SerializationError(f"Unable to write overlay: {path}")


def write_document_artifacts(
    run_directory: Path,
    document: DocumentResult,
    source_bgr: np.ndarray | None,
    crops: dict[str, np.ndarray],
) -> Path:
    """Persist a document without changing its raw OCR text or source image."""

    started = perf_counter()
    target = run_directory / "documents" / document.document_id
    target.mkdir(parents=True, exist_ok=False)
    crop_dir = target / "crops"
    crop_dir.mkdir()
    for region in document.regions:
        crop = crops.get(region.region_id)
        if crop is None:
            continue
        crop_path = crop_dir / f"{region.region_id}.png"
        if not cv2.imwrite(str(crop_path), crop):
            raise SerializationError(f"Unable to write crop: {crop_path}")
        region.crop_path = (Path("crops") / crop_path.name).as_posix()
    if source_bgr is None:
        document.errors.append("overlay_skipped_missing_source_image")
    else:
        _write_overlay(target / "overlay.png", source_bgr, document.regions)
    (target / "raw.txt").write_text(document.document_text_raw, encoding="utf-8")

    document_path = target / "document.json"
    preliminary = to_data(document)
    validate_payload(preliminary)
    document_path.write_text(json.dumps(preliminary, ensure_ascii=False, indent=2), encoding="utf-8")
    document.timing["serialization_ms"] = (perf_counter() - started) * 1000.0
    final_payload = to_data(document)
    validate_payload(final_payload)
    document_path.write_text(json.dumps(final_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_run_manifest(run_directory: Path, payload: dict[str, Any]) -> Path:
    validate_payload(payload)
    target = run_directory / "run_manifest.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def configuration_fingerprint(config_data: dict[str, Any]) -> str:
    return canonical_sha256(config_data)
