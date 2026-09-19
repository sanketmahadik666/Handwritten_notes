"""Command-line entry points for doctor and raw OCR execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .adapter import PaddleX37Adapter, PaddleXCompatibilityError
from .config import ConfigError, RunConfig, load_config
from .correction import skipped_correction
from .doctor import doctor_report
from .evaluation import aggregate_evaluations, evaluate_raw_text, load_ground_truth
from .hashing import sha256_file
from .image_io import ImageInputError, discover_images, load_image
from .results import DocumentResult, EvaluationRecord, RegionResult
from .serialization import (
    configuration_fingerprint,
    document_id,
    new_run_directory,
    write_document_artifacts,
    write_run_manifest,
)


def _region_result(adapter_region: Any) -> RegionResult:
    region_id = (
        f"line-{adapter_region.sorted_index:04d}"
        if adapter_region.sorted_index is not None
        else f"detector-{adapter_region.detector_index:04d}"
    )
    return RegionResult(
        region_id=region_id,
        detector_index=adapter_region.detector_index,
        sorted_index=adapter_region.sorted_index,
        raw_polygon=adapter_region.raw_polygon,
        sorted_polygon=adapter_region.sorted_polygon,
        detector_score=adapter_region.detector_score,
        crop_path=None,
        crop_provenance={
            "source_document": None,
            "detector_index": adapter_region.detector_index,
            "sorted_index": adapter_region.sorted_index,
            "polygon_coordinate_space": "source_image",
            "generation_method": adapter_region.metadata.get("crop_generation_method"),
            "status": adapter_region.crop_status,
        },
        raw_text=adapter_region.raw_text,
        recognition_score=adapter_region.recognition_score,
        recognition_order=adapter_region.recognition_order,
        correction=skipped_correction(),
        timing={"crop_ms": None, "recognition_ms": None},
        metadata=adapter_region.metadata,
    )


def _document_text(regions: list[RegionResult]) -> str:
    ordered = sorted(
        (region for region in regions if region.sorted_index is not None and region.raw_text is not None),
        key=lambda region: region.sorted_index,
    )
    return "\n".join(region.raw_text for region in ordered)


def _pipeline_metadata(runtime: dict[str, Any]) -> dict[str, Any]:
    versions = runtime.get("versions") or {}
    detector = runtime.get("detector") or {}
    recognizer = runtime.get("recognizer") or {}
    return {
        "paddleocr_version": versions.get("paddleocr"),
        "paddlex_version": versions.get("paddlex"),
        "paddlepaddle_version": versions.get("paddlepaddle"),
        "detector_model": detector.get("model_name"),
        "recognizer_model": recognizer.get("model_name"),
        "detector_device": detector.get("device"),
        "recognizer_device": recognizer.get("device"),
        "coordinate_space": "source_image",
        "ordering": "PaddleX SortQuadBoxes",
    }


def _failed_document(
    *,
    source_image: str,
    source_path: str,
    source_image_sha256: str,
    runtime: dict[str, Any],
    error: str,
    image_metadata: dict[str, Any] | None = None,
    timing: dict[str, float | None] | None = None,
) -> DocumentResult:
    return DocumentResult(
        document_id=document_id(source_image, source_image_sha256),
        source_image=source_image,
        source_path=source_path,
        source_image_sha256=source_image_sha256,
        image_metadata=image_metadata or {},
        pipeline_metadata=_pipeline_metadata(runtime),
        regions=[],
        document_text_raw="",
        document_text_corrected=None,
        evaluation=EvaluationRecord(ground_truth_available=False, status="document_failed"),
        timing=timing or {"image_load_ms": None, "serialization_ms": None},
        status="failed",
        errors=[error],
    )


def _document_summary(document: DocumentResult, document_directory: Path, run_directory: Path) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "source_image": document.source_image,
        "source_image_sha256": document.source_image_sha256,
        "document_path": document_directory.relative_to(run_directory).as_posix(),
        "status": document.status,
        "region_count": len(document.regions),
        "evaluation_status": document.evaluation.status,
        "errors": list(document.errors),
    }


def _run(config: RunConfig, input_path: str, output_root: str, ground_truth_path: str | None) -> Path:
    config_sha256 = configuration_fingerprint(config.to_dict())
    run_id, run_directory, created_at = new_run_directory(output_root, config_sha256)
    input_root, image_paths = discover_images(input_path)
    entries = load_ground_truth(ground_truth_path) if ground_truth_path else None
    adapter = PaddleX37Adapter(config)
    runtime = adapter.runtime_observation()
    document_summaries: list[dict[str, Any]] = []
    evaluations = []

    for source_path in image_paths:
        load_started = perf_counter()
        try:
            image = load_image(source_path, input_root)
        except ImageInputError as exc:
            document = _failed_document(
                source_image=source_path.name,
                source_path=source_path.relative_to(input_root).as_posix() if source_path.is_relative_to(input_root) else source_path.name,
                source_image_sha256=sha256_file(source_path),
                runtime=runtime,
                error=str(exc),
                timing={"image_load_ms": (perf_counter() - load_started) * 1000.0, "serialization_ms": None},
            )
            document_directory = write_document_artifacts(run_directory, document, None, {})
            document_summaries.append(_document_summary(document, document_directory, run_directory))
            evaluations.append(document.evaluation)
            continue

        image_load_ms = (perf_counter() - load_started) * 1000.0
        try:
            output = adapter.process(image.bgr_image)
        except (PaddleXCompatibilityError, ValueError, RuntimeError) as exc:
            document = _failed_document(
                source_image=image.source_path.name,
                source_path=image.relative_path,
                source_image_sha256=image.source_image_sha256,
                runtime=runtime,
                error=str(exc),
                image_metadata={
                    "width": image.width,
                    "height": image.height,
                    "channels": image.original_channels,
                    "input_handling": image.input_handling,
                },
                timing={"image_load_ms": image_load_ms, "serialization_ms": None},
            )
            document_directory = write_document_artifacts(run_directory, document, image.bgr_image, {})
            document_summaries.append(_document_summary(document, document_directory, run_directory))
            evaluations.append(document.evaluation)
            continue

        doc_id = document_id(image.source_path.name, image.source_image_sha256)
        regions = [_region_result(region) for region in output.regions]
        for region in regions:
            region.crop_provenance["source_document"] = doc_id
        raw_text = _document_text(regions)
        evaluation = evaluate_raw_text(image.source_path.name, raw_text, entries, config.evaluation)
        document = DocumentResult(
            document_id=doc_id,
            source_image=image.source_path.name,
            source_path=image.relative_path,
            source_image_sha256=image.source_image_sha256,
            image_metadata={
                "width": image.width,
                "height": image.height,
                "channels": image.original_channels,
                "input_handling": image.input_handling,
            },
            pipeline_metadata=_pipeline_metadata(runtime),
            regions=regions,
            document_text_raw=raw_text,
            document_text_corrected=None,
            evaluation=evaluation,
            timing={"image_load_ms": image_load_ms, **output.timing, "serialization_ms": None},
        )
        crops = {
            region_result.region_id: adapter_region.crop
            for region_result, adapter_region in zip(regions, output.regions)
            if adapter_region.crop is not None
        }
        document_directory = write_document_artifacts(run_directory, document, image.bgr_image, crops)
        document_summaries.append(_document_summary(document, document_directory, run_directory))
        evaluations.append(evaluation)

    failed = any(item["status"] != "success" for item in document_summaries)
    manifest = {
        "run_id": run_id,
        "created_at_utc": created_at,
        "project_version": "0.1.0",
        "config_sha256": config_sha256,
        "requested_configuration": config.to_dict(),
        "runtime": runtime,
        "documents": document_summaries,
        "aggregate_evaluation": aggregate_evaluations(evaluations),
        "integration_status": "runtime_pipeline_executed_with_document_errors" if failed else "runtime_pipeline_executed",
    }
    write_run_manifest(run_directory, manifest)
    return run_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handwritten_ocr", description="Auditable raw handwritten-English OCR baseline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="validate the pinned runtime and PaddleX compatibility contract")
    doctor.add_argument("--config", default="config/baseline.yaml", help="requested baseline YAML")
    run = subcommands.add_parser("run", help="run raw OCR over one image or a directory")
    run.add_argument("--input", required=True, help="image file or directory")
    run.add_argument("--config", default="config/baseline.yaml", help="requested baseline YAML")
    run.add_argument("--output-root", required=True, help="directory in which to create a unique run")
    run.add_argument("--ground-truth", help="optional verified ground-truth JSON manifest")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        config = load_config(arguments.config)
        if arguments.command == "doctor":
            print(json.dumps(doctor_report(config), ensure_ascii=False, indent=2))
            return 0
        run_directory = _run(config, arguments.input, arguments.output_root, arguments.ground_truth)
        print(json.dumps({"run_directory": str(run_directory)}, ensure_ascii=False))
        return 0
    except (ConfigError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
        return 2
