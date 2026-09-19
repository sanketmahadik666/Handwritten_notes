from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
import uuid
from datetime import datetime, timezone

from .events import broadcaster
from .schemas import (
    ProviderListResponse,
    ProviderCreateRequest,
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    RetryNotesResponse,
    RetryOcrResponse
)

app = FastAPI(title="Notes App API")

# Simple in-memory mock state for jobs and providers to meet the contract layout
# In a real system, these would interact with the db or orchestrator
_providers = [
    {
        "id": "ollama-local",
        "label": "Ollama (local, free)",
        "protocol": "openai_compatible",
        "enabled": True,
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.2",
        "has_api_key": False
    }
]

_jobs = {}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "ocr_runtime": {
            "paddleocr": "3.7.0",
            "paddlepaddle": "3.3.1",
            "requested_engine": None,
            "omp_num_threads": 1
        },
        "providers": [
            {
                "id": "ollama-local",
                "available": True,
                "latency_ms": 28
            },
            {
                "id": "groq-free",
                "available": True,
                "latency_ms": 140
            }
        ]
    }

@app.get("/api/providers", response_model=ProviderListResponse)
async def list_providers():
    return {
        "default_provider_id": "ollama-local",
        "providers": _providers
    }

@app.post("/api/providers", status_code=201)
async def create_provider(provider: ProviderCreateRequest):
    _providers.append({
        "id": provider.id,
        "label": provider.label,
        "protocol": provider.protocol,
        "enabled": True,
        "base_url": provider.base_url,
        "model": provider.model,
        "has_api_key": bool(provider.api_key)
    })
    return {"status": "created"}

@app.post("/api/jobs", status_code=202, response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    job_id = f"job-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    
    # Store minimal mock state to support the job status endpoint
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "provider_id": request.provider_id or "ollama-local",
        "pages": [
            {
                "document_id": f"page-{i}",
                "index": i,
                "status": "queued",
                "has_overlay": False,
                "has_notes": False
            } for i in range(len(request.file_paths))
        ]
    }
    
    return {
        "job_id": job_id,
        "total_pages": len(request.file_paths),
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    if job_id not in _jobs:
        return JSONResponse({"detail": "Job not found"}, status_code=404)
    return _jobs[job_id]

@app.get("/api/jobs/{job_id}/pages/{document_id}/notes.md")
async def get_page_notes(job_id: str, document_id: str):
    # Mock response, actual implementation reads from filesystem
    return PlainTextResponse(
        "# Example Notes\n\n## Summary\nMock notes file.",
        media_type="text/markdown; charset=utf-8"
    )

@app.get("/api/jobs/{job_id}/pages/{document_id}/raw.txt")
async def get_page_raw(job_id: str, document_id: str):
    # Mock response, actual implementation reads from filesystem
    return PlainTextResponse(
        "Mock raw text from OCR.",
        media_type="text/plain; charset=utf-8"
    )

@app.post("/api/jobs/{job_id}/pages/{document_id}/retry-notes", status_code=202, response_model=RetryNotesResponse)
async def retry_notes(job_id: str, document_id: str):
    return {
        "status": "notes_queued",
        "document_id": document_id
    }

@app.post("/api/jobs/{job_id}/pages/{document_id}/retry-ocr", status_code=202, response_model=RetryOcrResponse)
async def retry_ocr(job_id: str, document_id: str):
    return {
        "status": "queued",
        "document_id": document_id
    }

@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    return StreamingResponse(
        broadcaster.sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
