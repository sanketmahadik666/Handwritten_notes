"""Orchestration layer for page-by-page OCR processing."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from time import perf_counter
from typing import Any

from .adapter import PaddleX37Adapter, PaddleXCompatibilityError
from .config import RunConfig
from .correction import skipped_correction
from .db import Database
from .hashing import sha256_file
from .image_io import ImageInputError, discover_images, load_image
from .models import Job, PageJob
from .queue import QueueWorker
from .results import DocumentResult, EvaluationRecord, RegionResult
from .serialization import write_document_artifacts
from .service import JobService

logger = logging.getLogger(__name__)


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


class OrchestratorService:
    def __init__(self, db: Database, config: RunConfig, output_root: str | Path):
        self.db = db
        self.config = config
        self.output_root = Path(output_root)
        self.job_service = JobService(db)
        self.queue_worker = QueueWorker(db, max_retries=config.app.max_retries if config.app else 3)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def create_job(self, document_id: str, page_count: int, config_fingerprint: str | None = None) -> Job:
        job = self.job_service.create_job(document_id, page_count, config_fingerprint)
        logger.info(f"Created job {job.job_id} with {page_count} pages")
        return job

    def start_orchestrator(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._orchestrator_loop, daemon=True)
        self._thread.start()
        logger.info("Orchestrator started")

    def stop_orchestrator(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        logger.info("Orchestrator stopped")

    def get_job(self, job_id: str) -> Job:
        return self.job_service.get_job(job_id)

    def get_pages(self, job_id: str) -> list[PageJob]:
        return self.job_service.get_job_pages(job_id)

    def get_page(self, page_job_id: str) -> PageJob:
        return self.job_service.get_page_job(page_job_id)

    def retry_page(self, page_job_id: str) -> PageJob:
        page = self.job_service.retry_page(page_job_id)
        logger.info(f"Retrying page {page.page_job_id} (job {page.job_id})")
        return page

    def _orchestrator_loop(self) -> None:
        # On startup, recover any interrupted pages
        recovered = self.queue_worker.recover_interrupted()
        if recovered > 0:
            logger.info(f"Recovered {recovered} interrupted pages")

        adapter = None
        runtime = {}

        poll_interval = self.config.app.queue_poll_interval_seconds if self.config.app else 5

        while not self._stop_event.is_set():
            page = self.queue_worker.claim_next()
            if not page:
                # No work, wait before polling again
                self._stop_event.wait(poll_interval)
                continue

            logger.info(f"Claimed page {page.page_number} for job {page.job_id} (attempt {page.attempt_count})")
            
            try:
                if adapter is None:
                    adapter = PaddleX37Adapter(self.config)
                    runtime = adapter.runtime_observation()

                job = self.job_service.get_job(page.job_id)
                input_root, image_paths = discover_images(job.document_id)
                
                if page.page_number < 1 or page.page_number > len(image_paths):
                    raise ValueError(f"Page number {page.page_number} out of bounds (1-{len(image_paths)})")
                
                source_path = image_paths[page.page_number - 1]
                
                load_started = perf_counter()
                image = load_image(source_path, input_root)
                image_load_ms = (perf_counter() - load_started) * 1000.0

                output = adapter.process(image.bgr_image)

                doc_id = f"page-{page.page_number:04d}"
                regions = [_region_result(r) for r in output.regions]
                for r in regions:
                    r.crop_provenance["source_document"] = doc_id

                raw_text = _document_text(regions)
                evaluation = EvaluationRecord(ground_truth_available=False, status="not_evaluated")

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

                run_directory = self.output_root / job.job_id / f"attempt-{page.attempt_count}"
                document_directory = write_document_artifacts(run_directory, document, image.bgr_image, crops)

                raw_text_path = document_directory / "raw.txt"
                raw_text_sha256 = sha256_file(raw_text_path)
                doc_json_path = document_directory / "document.json"

                self.queue_worker.mark_complete(
                    page.page_job_id,
                    raw_text_path.relative_to(self.output_root).as_posix(),
                    raw_text_sha256,
                    doc_json_path.relative_to(self.output_root).as_posix()
                )

                logger.info(f"Successfully processed page {page.page_number} for job {page.job_id}")

            except (ImageInputError, PaddleXCompatibilityError, ValueError, RuntimeError, Exception) as exc:
                logger.error(f"Error processing page {page.page_number} for job {page.job_id}: {exc}")
                self.queue_worker.mark_failed(page.page_job_id, str(exc))
