from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from handwritten_ocr.db import Database
from handwritten_ocr.service import JobNotFoundError, JobService

from .events import broadcaster
from .schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    PageStatusModel,
    ProviderCreateRequest,
    ProviderListResponse,
    RetryNotesResponse,
    RetryOcrResponse,
)


def create_app(database_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Notes App API")

    resolved_database_path = database_path or os.environ.get(
        "HANDWRITTEN_OCR_DB",
        ".local/jobs.sqlite3",
    )
    database = Database(resolved_database_path)
    job_service = JobService(database)

    providers = [
        {
            "id": "ollama-local",
            "label": "Ollama (local, free)",
            "protocol": "openai_compatible",
            "enabled": True,
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "llama3.2",
            "has_api_key": False,
        }
    ]

    jobs: dict[str, dict] = {}

    @app.get("/api/health")
    async def health_check():
        return {
            "status": "unavailable",
            "ocr_runtime": None,
            "providers": [],
        }

    @app.get("/api/providers", response_model=ProviderListResponse)
    async def list_providers():
        return {
            "default_provider_id": "ollama-local",
            "providers": providers,
        }

    @app.post("/api/providers", status_code=201)
    async def create_provider(provider: ProviderCreateRequest):
        providers.append(
            {
                "id": provider.id,
                "label": provider.label,
                "protocol": provider.protocol,
                "enabled": True,
                "base_url": provider.base_url,
                "model": provider.model,
                "has_api_key": bool(provider.api_key),
            }
        )
        return {"status": "created"}

    @app.post("/api/jobs", status_code=202, response_model=JobCreateResponse)
    async def create_job(request: JobCreateRequest):
        job_id = (
            f"job-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{uuid.uuid4().hex[:6]}"
        )

        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "provider_id": request.provider_id,
            "pages": [],
        }

        return {
            "job_id": job_id,
            "total_pages": len(request.file_paths),
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str) -> JobStatusResponse:
        try:
            job = job_service.get_job(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

        pages = job_service.get_job_pages(job_id)

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status.value,
            provider_id=None,
            pages=[
                PageStatusModel(
                    document_id=page.document_id,
                    index=page.page_number - 1,
                    status=page.status.value,
                    raw_sha256=page.raw_text_sha256,
                    has_overlay=page.overlay_path is not None,
                    has_notes=False,
                )
                for page in pages
            ],
        )

    @app.get("/api/jobs/{job_id}/pages/{document_id}/notes.md")
    async def get_page_notes(job_id: str, document_id: str):
        return PlainTextResponse(
            "# Example Notes\n\n## Summary\nMock notes file.",
            media_type="text/markdown",
        )

    @app.get("/api/jobs/{job_id}/pages/{document_id}/raw.txt")
    async def get_page_raw(job_id: str, document_id: str):
        return PlainTextResponse(
            "Mock raw text from OCR.",
            media_type="text/plain",
        )

    @app.post(
        "/api/jobs/{job_id}/pages/{document_id}/retry-notes",
        status_code=202,
        response_model=RetryNotesResponse,
    )
    async def retry_notes(job_id: str, document_id: str):
        return {
            "status": "notes_queued",
            "document_id": document_id,
        }

    @app.post(
        "/api/jobs/{job_id}/pages/{document_id}/retry-ocr",
        status_code=202,
        response_model=RetryOcrResponse,
    )
    async def retry_ocr(job_id: str, document_id: str):
        return {
            "status": "queued",
            "document_id": document_id,
        }

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str):
        return StreamingResponse(
            broadcaster.sse_generator(job_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()