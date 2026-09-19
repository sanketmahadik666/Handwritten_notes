# Phase 4 — Service-Oriented OCR Work Queue Guide

## Purpose

This document is the final handoff for the next coding agent.

It is a clean, service-focused continuation instruction built from the earlier OCR and orchestration notes. It is intended to guide implementation of the next layer without rewriting the existing OCR baseline or modifying the verified runtime.

This phase is about service orchestration and job/page execution flow. It is not a greenfield rewrite of the project.

---

## Scope and boundary

In scope:
- service-layer orchestration for OCR jobs
- persistent job and page records
- queue claim and processing logic
- artifact writing per page
- retry and failure isolation
- startup recovery and lifecycle management
- minimal service/API interfaces for orchestration
- tests for queue/job processing behavior

Out of scope:
- AI notes generation
- provider registry and model settings
- SSE/event streaming UI layer
- frontend work
- LLM correction
- modifying the verified OCR runtime
- changing the pinned PaddleOCR/PaddleX stack
- custom reading-order logic in the OCR path

This is a hard boundary. Do not implement notes, provider, UI, or AI work in this phase.

---

## Cross-check summary

The existing guidance documents are directionally consistent, but they mix multiple phases together:
- OCR baseline rules
- notes application goals
- queue and orchestration requirements
- frontend/API ambition

This Phase 4 guide resolves that by narrowing the agent to the service layer only:
- preserve the OCR baseline
- orchestrate work across pages
- keep state and artifacts persisted
- operate safely under retries and failures

The project should continue from the existing codebase, not be rebuilt.

---

## Existing project state to preserve

The next agent must treat the existing implementation as the source of truth.

Required runtime pins remain unchanged:
- Python 3.12.10
- PaddleOCR 3.7.0
- PaddleX 3.7.2
- PaddlePaddle 3.3.1
- NumPy 2.3.5
- OpenCV 4.10.0
- OMP_NUM_THREADS=1
- models: PP-OCRv6_medium_det and PP-OCRv6_medium_rec
- requested_engine remains null
- optional document preprocessing remains disabled
- model preprocessing remains PaddleX-managed
- correction.status remains skipped

Do not upgrade, downgrade, or replace the OCR environment.

---

## Architecture responsibilities

Keep responsibilities separated:

1. Orchestrator
   - coordinates job execution
   - claims queue items
   - updates statuses
   - invokes OCR per page
   - manages retries and recovery

2. Persistent queue
   - authoritative record of pending and active work
   - atomic claim semantics
   - prevents duplicate active processing

3. OCR adapter
   - runs OCR for one image only
   - returns page-local OCR result data
   - uses the existing adapter contract, not a duplicate implementation

4. Artifact writer
   - writes page-level OCR outputs
   - persists raw OCR, document JSON, overlay, and crops
   - writes hashes and result metadata

5. Job repository
   - stores page and job state
   - tracks attempts, timestamps, errors, and output paths
   - derives aggregate job status transactionally

6. Configuration
   - OCR worker count
   - output root
   - retry policy
   - startup recovery rules

The orchestrator must not contain PaddleOCR-specific internals.

---

## Required processing flow

For every queued page the service must:

1. Claim the next eligible queue item atomically.
2. Mark page status as ocr_running.
3. Record start timestamp and attempt count.
4. Resolve and validate the image path.
5. Invoke the OCR adapter for that page only.
6. Persist artifact outputs for that page in a unique directory.
7. Validate that required outputs were written.
8. Compute SHA-256 hashes for raw OCR and relevant artifacts.
9. Update page metadata and mark the page as ocr_complete.
10. Recalculate parent job state and counters transactionally.
11. Continue to the next eligible page.

No page may be merged with another page in one OCR request unless the existing adapter explicitly requires it and preserves page isolation.

---

## Artifact model and directory structure

Follow the existing project conventions when present. If no existing convention is available, use a deterministic structure equivalent to:

```text
output/
  <job_id>/
    pages/
      page-0001/
        document.json
        raw.txt
        overlay.png
        crops/
      page-0002/
        document.json
        raw.txt
        overlay.png
        crops/
```

Requirements:
- per-page unique artifact directory
- source image preserved
- no cross-page overwrite
- no overwrite of prior successful artifacts during retry
- unique attempt directory where necessary
- persist final artifact paths and hashes in the page record
- use atomic writes when practical
- do not mark completion before all required artifact writes succeed
- keep machine-specific paths out of OCR raw text
- do not rewrite OCR text to remove boilerplate or fix recognition errors

If artifact write fails, the page must be marked failed and retain enough diagnostic detail for root-cause review.

---

## Immutable OCR output policy

OCR output is evidence and must remain immutable.

Preserve:
- raw OCR text exactly as produced by the serializer
- detected lines and reading order
- recognition confidence when actually exposed
- original-coordinate polygons when available
- crop status and artifact references when available
- existing provenance and config metadata

Do not:
- correct OCR spelling or punctuation
- add LLM-based cleanup
- remove printed labels such as Name:
- fabricate scores, engines, or backend names
- reorder lines by text matching
- replace missing metadata with invented values

If a field is unavailable, keep the existing null/unknown convention.

---

## Failure handling and isolation

A page failure must not block processing of other pages in the same job.

Examples:
- missing or corrupt source image
- OCR adapter initialization failure
- inference failure
- artifact serialization failure
- disk permission or write failure
- hashing failure
- database write failure

Per page:
- persist a meaningful error
- mark page as ocr_failed when safely recordable
- do not mark as ocr_complete unless all required outputs are committed
- continue processing other eligible pages
- preserve prior completed artifacts
- avoid indefinite retry loops

Distinguish OCR errors from orchestration or persistence errors in logs and stored metadata.

If SQLite is unavailable, do not claim the page was successfully persisted; stop safely and report infrastructure failure.

---

## Retry semantics

Support explicit retry of failed OCR pages through the service/repo interface.

Retry must:
1. validate retry eligibility
2. create a fresh attempt or attempt directory
3. keep earlier attempt artifacts and errors for audit trail
4. re-enqueue the page transactionally
5. reset only the fields appropriate for a new attempt
6. avoid duplicate queue entries
7. leave successful pages untouched

Do not silently retry successful pages.

If the project has an existing automatic retry policy, honor it. Otherwise implement explicit retry only.

---

## Job lifecycle and progress model

Use the established page states:

- queued
- ocr_running
- ocr_complete
- ocr_failed

Retry cycle:
- ocr_failed -> queued

Parent job state must be derived from persisted page records rather than in-memory counters.

Requirements:
- completed pages remain visible while later pages continue
- one failed page does not erase other progress
- aggregate counts remain consistent after retry
- a job is not complete while queued or running pages remain
- reopening the system must not lose queued or completed page state

This phase does not implement notes-related states beyond compatibility with the existing model.

---

## Concurrency policy

For this phase:
- OCR worker concurrency remains 1
- only one page is processed by OCR at a time
- queue claiming must be atomic and duplicate-safe
- do not parallelize OCR across pages
- keep design ready for a future notes queue without implementing it now

---

## Configuration requirements

Use existing application configuration wherever possible.

Support or validate:
- OCR worker concurrency default = 1
- output root
- page artifact layout
- startup recovery behavior
- retry policy
- whether orchestration starts automatically or via service call

Reject unsupported concurrency settings instead of silently ignoring them.

Do not add AI provider or notes configuration in this phase.

---

## Service interface

Expose service-level operations equivalent to:

```python
create_job(document) -> Job
start_orchestrator() -> None
stop_orchestrator() -> None
get_job(job_id) -> Job
get_pages(job_id) -> list[PageJob]
get_page(page_job_id) -> PageJob
retry_page(page_job_id) -> PageJob
```

Use existing APIs and names if present.

The service must function without requiring a frontend.

Shutdown behavior:
- stop accepting new work
- allow the active page to finish when practical
- if the active page is interrupted, use documented startup recovery behavior

---

## Testing requirements

Use the existing test framework; prefer unittest where no broader framework is established.

Important tests:
1. multiple pages processed independently
2. FIFO ordering preserved
3. only one OCR page active at a time
4. each page gets a unique artifact directory
5. OCR outputs and hashes persisted
6. failed page does not stop subsequent pages
7. missing or corrupt image fails only its own page
8. artifact-write failure does not falsely mark page complete
9. explicit retry preserves earlier artifacts and creates new attempt state
10. completed pages are not reprocessed accidentally
11. parent job status and counts remain correct
12. restart preserves queued and completed work
13. interrupted ocr_running work follows configured recovery policy
14. duplicate queue claims prevented
15. shutdown does not corrupt page state
16. existing OCR baseline tests remain unchanged and pass

If available, include one controlled integration test using the exact interpreter and installed runtime.

Do not invent accuracy numbers. Historical data must remain historical unless independently rerun.

---

## Logging and observability

Log structured events for:
- job created
- page claimed
- OCR started
- OCR completed
- OCR failed
- artifacts committed
- page retried
- recovery action taken
- orchestrator stopped

Include job ID, page number, attempt count, elapsed time, and error category when available.

Do not log secrets or expose machine-specific paths unnecessarily.

---

## Deliverables expected from the agent

After implementation, the agent must report:
1. existing architecture discovered
2. files created or modified
3. orchestrator and worker lifecycle
4. artifact layout and immutability guarantees
5. retry and failure semantics
6. configuration changes
7. tests run and actual results
8. unresolved limitations

Do not claim tests passed unless they were actually executed.

---

## Final continuation prompt for the next AI agent

```text
Implement the next service-focused phase only: OCR orchestration and job/page processing.

Context:
- The OCR baseline already exists and is the source of truth.
- Keep the verified runtime and package behavior unchanged.
- Runtime pins remain: Python 3.12.10, PaddleOCR 3.7.0, PaddleX 3.7.2, PaddlePaddle 3.3.1, NumPy 2.3.5, OpenCV 4.10.0, OMP_NUM_THREADS=1.
- requested_engine stays null.
- Do not implement AI notes, provider registry, frontend, UI, or SSE in this phase.

Objectives:
1. Build page-by-page OCR orchestration using existing job/page and queue storage if available.
2. Add or complete a service abstraction for job creation, orchestration startup, page processing, and retry.
3. Maintain one active OCR page at a time; queue claims must be atomic and safe.
4. Persist per-page artifact directories containing raw OCR, document metadata, overlays, and crops.
5. Ensure outputs remain immutable and hash-backed.
6. Mark failed pages without stopping other queued pages.
7. Support explicit retry logic for failed OCR pages only.
8. Keep job and page state consistent after retries and restarts.
9. Use unittest-style tests with temp directories and mocked OCR adapters.

Requirements:
- Keep the OCR baseline untouched.
- Keep the existing adapter contract and version guards.
- Do not silently switch OCR backends.
- Do not fabricate engine or confidence values.
- Do not rewrite raw OCR text.
- Do not overwrite successful artifacts during retry.
- Do not let one page failure cancel the rest of the job.
- Do not implement notes or UI concerns in this phase.

Deliverables:
- orchestration code
- job/page queue processing
- artifact persistence and immutability enforcement
- retry and failure isolation
- tests covering queue behavior, job status integrity, and page independence
- concise status report listing what was built and what was verified
```

---

## Final instruction

This phase is not a rewrite of the OCR baseline and not a notes app. It is the service layer that safely executes and tracks OCR work across pages while preserving the integrity of the underlying OCR evidence.

The agent should protect the existing OCR system, avoid scope creep, and keep the implementation narrow, auditable, and testable.
