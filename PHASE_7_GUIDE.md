# Phase 7 — Service API and SSE Contract Guide

## Purpose

This document is the final implementation handoff for the next coding agent.

It is based on the supplied API/SSE specification and focuses strictly on the service layer: HTTP endpoints, event publication, and job progress contract. It does not ask the agent to modify the OCR baseline or rewrite the project.

The objective is to implement the service contract in a way that is consistent with the existing OCR work and the page/job orchestration pattern already described in the earlier phase documents.

---

## Scope boundary

In scope:
- API server and route definitions
- SSE event channel implementation
- event schema and payload contract
- job and page status endpoints
- provider registry/list endpoints
- health check endpoints
- retry endpoints for OCR or notes stages
- service-layer job state exposure through HTTP and event stream

Out of scope:
- changing the OCR runtime or model stack
- rewriting the OCR baseline behavior
- AI notes generation logic
- frontend UI implementation
- provider protocol implementation beyond the API contract required by the service layer
- changing the repository structure beyond the declared service files

This is a strict boundary. Implement only the service/event layer described here.

---

## Contract to implement

The implementation must match the provided contract for the following files:

- notes_app/server.py
- notes_app/events.py
- notes_app/schemas.py

The service must expose the following SSE endpoint:

- GET /api/jobs/{job_id}/events

Headers:
- Content-Type: text/event-stream
- Cache-Control: no-cache
- Connection: keep-alive
- X-Accel-Buffering: no

Heartbeat behavior:
- heartbeat every 15 seconds
- keep the connection alive even when no event is emitted

---

## SSE event contract

The following events are authoritative and must be emitted in the specified shape.

### 1) job.started
Payload:
```json
{
  "type": "job.started",
  "job_id": "string",
  "total_pages": 12,
  "provider_id": "string",
  "started_at": "ISO8601 string"
}
```

When to emit:
- when orchestrator initializes document processing

### 2) page.ocr_started
Payload:
```json
{
  "type": "page.ocr_started",
  "job_id": "string",
  "document_id": "string",
  "index": 0,
  "attempt": 1
}
```

When to emit:
- when the single-page OCR worker atomically claims a page

### 3) page.ocr_complete
Payload:
```json
{
  "type": "page.ocr_complete",
  "job_id": "string",
  "document_id": "string",
  "raw_sha256": "string",
  "raw_path": "string",
  "duration_ms": 123
}
```

When to emit:
- immediately after raw.txt and document.json are committed

### 4) page.notes_started
Payload:
```json
{
  "type": "page.notes_started",
  "job_id": "string",
  "document_id": "string",
  "provider_id": "string",
  "model": "string"
}
```

When to emit:
- when the AI notes worker starts for that page

### 5) page.notes_delta
Payload:
```json
{
  "type": "page.notes_delta",
  "job_id": "string",
  "document_id": "string",
  "delta": "string"
}
```

When to emit:
- optional streaming token updates from an OpenAI-compatible provider

### 6) page.notes_complete
Payload:
```json
{
  "type": "page.notes_complete",
  "job_id": "string",
  "document_id": "string",
  "notes_path": "string",
  "status": "succeeded"
}
```

When to emit:
- after notes.md and notes.json are validated and written

### 7) page.failed
Payload:
```json
{
  "type": "page.failed",
  "job_id": "string",
  "document_id": "string",
  "stage": "ocr | notes",
  "error": "string",
  "retryable": true
}
```

When to emit:
- on terminal failure for either stage without failing the entire job

### 8) job.finished
Payload:
```json
{
  "type": "job.finished",
  "job_id": "string",
  "status": "completed | completed_with_errors",
  "total_pages": 12,
  "completed_pages": 10,
  "failed_pages": 2
}
```

When to emit:
- when all queued pages have reached terminal states

---

## Event bus implementation requirements

The implementation must provide a broadcaster with these semantics:
- subscribers keyed by job id
- safe queueing with bounded size
- no event loss for active subscribers under normal operation
- graceful disconnect on unsubscribe
- SSE generator that yields heartbeat when idle

The provided reference implementation is authoritative in structure and intent:

```python
import asyncio
import json
from typing import AsyncGenerator, Dict, Set

class JobEventBroadcaster:
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        async with self._lock:
            q = asyncio.Queue(maxsize=100)
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add(q)
            return q

    async def unsubscribe(self, job_id: str, q: asyncio.Queue):
        async with self._lock:
            if job_id in self._subscribers:
                self._subscribers[job_id].discard(q)
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    async def publish(self, job_id: str, event_type: str, data: dict):
        async with self._lock:
            queues = list(self._subscribers.get(job_id, []))
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def sse_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        queue = await self.subscribe(job_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await self.unsubscribe(job_id, queue)

broadcaster = JobEventBroadcaster()
```

The agent must implement the same logic pattern, adapted to the project if necessary, but without changing the intended behavior.

---

## HTTP endpoint contract

These are the required endpoints and behaviors.

### GET /api/health
Summary:
- OCR runtime doctor summary and provider connectivity test

Expected behavior:
- return 200
- include OCR runtime summary
- include provider availability check

Example response shape:
```json
{
  "status": "healthy",
  "ocr_runtime": {
    "paddleocr": "3.7.0",
    "paddlepaddle": "3.3.1",
    "requested_engine": null,
    "omp_num_threads": 1
  },
  "providers": [
    {
      "id": "ollama-local",
      "available": true,
      "latency_ms": 28
    },
    {
      "id": "groq-free",
      "available": true,
      "latency_ms": 140
    }
  ]
}
```

### GET /api/providers
Summary:
- list all configured notes providers

Return shape:
```json
{
  "default_provider_id": "ollama-local",
  "providers": [
    {
      "id": "ollama-local",
      "label": "Ollama (local, free)",
      "protocol": "openai_compatible",
      "enabled": true,
      "base_url": "http://127.0.0.1:11434/v1",
      "model": "llama3.2",
      "has_api_key": false
    }
  ]
}
```

### POST /api/providers
Summary:
- register a new provider

Request shape:
```json
{
  "id": "string",
  "label": "string",
  "protocol": "string",
  "base_url": "string",
  "model": "string",
  "api_key": "string or null",
  "timeout_s": 60,
  "max_tokens": 1200
}
```

Expected result:
- 201 Created
- provider stored in registry or config layer

### POST /api/jobs
Summary:
- create a new document ingestion job from uploaded images or directory paths

Request:
- provider_id: string or null
- file_paths: array of string or multipart files

Expected response:
```json
{
  "job_id": "job-20261010T120000Z-7a3b4c",
  "total_pages": 4,
  "status": "queued",
  "created_at": "2026-10-10T12:00:00Z"
}
```

Status code:
- 202 Accepted

### GET /api/jobs/{job_id}
Summary:
- return job state and page progress summary

Example:
```json
{
  "job_id": "job-20261010T120000Z-7a3b4c",
  "status": "processing",
  "provider_id": "ollama-local",
  "pages": [
    {
      "document_id": "a01-000u-f1764d425a84",
      "index": 0,
      "status": "notes_ready",
      "raw_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "has_overlay": true,
      "has_notes": true
    },
    {
      "document_id": "a01-001u-9843fa765b21",
      "index": 1,
      "status": "ocr_running",
      "has_overlay": false,
      "has_notes": false
    }
  ]
}
```

### GET /api/jobs/{job_id}/pages/{document_id}/notes.md
Summary:
- return rendered Markdown note file for a page

Headers:
- Content-Type: text/markdown; charset=utf-8

### GET /api/jobs/{job_id}/pages/{document_id}/raw.txt
Summary:
- return immutable OCR raw text

Headers:
- Content-Type: text/plain; charset=utf-8

### POST /api/jobs/{job_id}/pages/{document_id}/retry-notes
Summary:
- rerun the notes stage without redoing OCR

Expected response:
```json
{
  "status": "notes_queued",
  "document_id": "a01-001u-9843fa765b21"
}
```

Status code:
- 202 Accepted

### POST /api/jobs/{job_id}/pages/{document_id}/retry-ocr
Summary:
- rerun full OCR processing and artifact persistence for a failed page

Expected response:
```json
{
  "status": "queued",
  "document_id": "a01-001u-9843fa765b21"
}
```

Status code:
- 202 Accepted

---

## Implementation requirements for the agent

The next coding agent must:

1. Implement the HTTP endpoints described above.
2. Implement the SSE broadcaster exactly in spirit and behavior.
3. Keep event payloads consistent with the documented schemas.
4. Ensure the event stream stays alive with heartbeat output every 15 seconds.
5. Emit page and job events only when lifecycle states change.
6. Keep endpoints and event payloads stable enough for the front-end to subscribe and render job state.
7. Treat the event bus as a service layer responsibility, not a frontend concern.
8. Keep the design consistent with the earlier orchestrator/job/page state model.
9. Use the project’s existing patterns where possible rather than inventing a new architecture.
10. Do not modify the verified OCR runtime or ecosystem.

---

## Non-functional requirements

- API must be responsive and composable
- SSE must not stall when no new events are emitted
- endpoints must remain safe for multiple subscribers
- event payloads must be JSON stringifiable and small enough for streaming
- secrets must remain outside Git and not be embedded in source code
- provider status and health checks must be non-blocking and safe under partial service failures
- failure of one worker should not break the event stream for the job

---

## What not to do

Do not:
- change the OCR implementation or model stack
- create a new project architecture from scratch
- invent unsupported endpoints or event names
- add UI logic to the server layer
- silently change job semantics or lifecycle states
- store secrets in source control
- hardcode machine-specific or user-specific paths into the API contract

---

## Final continuation prompt for the next AI agent

```text
Implement the service layer for the OCR job system using the supplied API and SSE contract.

Context:
- This is a service-only phase.
- Do not rewrite or modify the OCR baseline runtime or package logic.
- This phase must implement the server, event bus, job state API, and SSE contract described in the provided spec.
- Keep the project structure aligned with the supplied file targets: notes_app/server.py, notes_app/events.py, notes_app/schemas.py.

Requirements:
1. Implement the HTTP endpoints listed in the contract: /api/health, /api/providers, /api/jobs, /api/jobs/{job_id}, /api/jobs/{job_id}/pages/{document_id}/notes.md, /api/jobs/{job_id}/pages/{document_id}/raw.txt, and retry routes.
2. Implement the SSE event broadcaster and keep the connection alive with heartbeats every 15 seconds.
3. Emit all required events exactly in the specified format: job.started, page.ocr_started, page.ocr_complete, page.notes_started, page.notes_delta, page.notes_complete, page.failed, job.finished.
4. Use the reference event bus pattern provided in the contract.
5. Keep the job/page model aligned with the project’s existing orchestration state model.
6. Keep the API contract stable and machine-readable.
7. Respect provider connectivity and health semantics without blocking the main service.
8. Keep configuration external and avoid embedding secrets in source.
9. Do not change the OCR engine, runtime, model stack, or project baseline logic.
10. Do not implement UI or frontend behavior in this phase.

Deliverables:
- working API server implementation
- working event broadcaster and SSE endpoint
- validated response schemas and event payloads
- operationally safe job and page status exposure
- concise status report with what was implemented and what was verified
```

---

## Final instruction

This phase is about the service layer only: exposing job state, event streaming, provider health metadata, retry routes, and the controlled API contract needed to support the rest of the application. The OCR baseline remains untouched and is treated as an existing dependency. The agent must mobilize the contract exactly as specified, without broad scope expansion or project rewriting.
