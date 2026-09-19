# Phase 3 — OCR Orchestration Guide

## Purpose

This document is the final handoff instruction for the next coding agent working on the next implementation phase only.

This phase is restricted to OCR orchestration. It does not implement AI notes generation, local provider registry, SSE, or frontend UI.

The goal is to add reliable page-by-page OCR orchestration using the existing OCR adapter, persistent queue, page/job state, and artifact writer already present in the workspace.

---

## Scope boundary

In scope:
- page-by-page OCR orchestration
- queue claim and processing workflow
- per-page state transitions
- artifact persistence per page
- retry handling and failure isolation
- startup recovery behavior
- service-level orchestration API
- unittest coverage for orchestration

Out of scope:
- AI note generation
- provider registry
- notes queue
- UI or frontend work
- SSE streaming
- LLM-based OCR correction
- notes provider compatibility work

This is a strict boundary. Do not implement any of the out-of-scope items in this phase.

---

## Current project state

The repo already contains the OCR baseline and supporting project artifacts.

Treat the existing OCR runtime and implementation as the source of truth:
- Python 3.12.10
- PaddleOCR 3.7.0
- PaddleX 3.7.2
- PaddlePaddle 3.3.1
- NumPy 2.3.5
- OpenCV 4.10.0
- OMP_NUM_THREADS=1
- models: PP-OCRv6_medium_det and PP-OCRv6_medium_rec
- requested_engine remains null
- document-level optional preprocessing remains disabled
- model preprocessing remains PaddleX-managed
- correction.status remains skipped

Do not modify or upgrade the verified OCR environment.

---

## Required architecture

Keep responsibilities separated and do not merge them into a single implementation object.

Required roles:

1. Orchestrator
   - coordinates page processing
   - claims queue items
   - updates job/page state
   - retries and recovery
   - calls the OCR adapter per page

2. Persistent queue
   - authoritative store for pending and claimed work
   - must prevent duplicate claims
   - must support explicit retry of failed pages

3. OCR adapter
   - runs OCR for one page only
   - returns an OCRPageResult-like object or equivalent wrapper
   - must use the existing OCR adapter contract, not a duplicate implementation

4. Artifact writer
   - creates one isolated output directory per page
   - writes immutable OCR outputs
   - writes raw OCR as persisted evidence
   - uses atomic writes where practical

5. Job repository
   - persists page/job metadata
   - updates status and counts transactionally
   - tracks attempts, timestamps, errors, and artifact paths

6. Configuration
   - worker concurrency
   - output root
   - retry policy
   - startup recovery behavior

The orchestrator must not contain PaddleOCR-specific internals.

---

## Mandatory processing flow

For every queued page, the worker must do the following:

1. Atomically claim the next eligible queue item.
2. Mark the page as ocr_running.
3. Record start time and increment attempt count.
4. Resolve and validate the image file.
5. Invoke the OCR adapter on that page only.
6. Persist OCR artifacts to a unique page output directory.
7. Verify required artifact writes succeeded.
8. Compute hash values for the raw OCR text and relevant artifacts.
9. Update page artifact metadata and mark page as ocr_complete.
10. Recalculate parent job status and page counts transactionally.
11. Move on to the next queued page.

Each page must be isolated. Do not combine multiple page images into one OCR request unless the existing adapter explicitly requires it and preserves page isolation.

---

## Artifact structure

Use the established project convention if it already exists. If not, use a deterministic page-level structure like:

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
- one isolated artifact directory per page
- original source image is preserved
- do not overwrite another page's artifacts
- do not overwrite prior completed results during retry
- unique attempt/run directory when necessary
- persist final artifact paths and hashes in the page record
- use atomic writes when practical
- do not mark page complete until required artifact writes succeed
- do not add machine-specific paths into OCR raw text
- do not modify OCR text to remove boilerplate or correct recognition errors

If artifact writing fails, mark the page as failed and preserve enough detail to diagnose the issue.

---

## Immutable OCR contract

Treat OCR output as immutable evidence.

Preserve:
- raw OCR text exactly as produced by the existing serializer
- detected text regions and reading order
- confidence scores when actually provided
- original-coordinate polygons where available
- crop status and artifact references where available
- OCR configuration and provenance already supported by the existing implementation

Do not:
- correct spelling or punctuation
- add LLM processing
- remove printed labels from raw OCR
- fabricate confidence scores, engine names, or backend details
- reorder lines by text matching
- replace missing metadata with invented values

If a field is unavailable, preserve the existing null/unknown convention.

---

## Preserve the existing OCR baseline

Do not change the established OCR runtime or implementation:
- PaddleOCR 3.7.0
- PaddleX 3.7.2
- PaddlePaddle 3.3.1
- PP-OCRv6 medium detector and recognizer
- existing CPU configuration and environmental settings
- optional document orientation, unwarping, and textline orientation disabled
- existing PaddleX detector, sorter, cropper, and recognition behavior

Do not force a new inference engine or silently fall back to another implementation.

Keep existing version guards and fail-closed behavior. If the OCR adapter cannot initialize, surface a clear startup or job error rather than substituting a different model.

---

## Failure isolation

A page failure must not stop processing other pages in the same job.

Examples:
- missing source image
- unsupported or corrupt image
- OCR initialization or inference failure
- artifact serialization failure
- disk write or permission failure
- hashing failure
- database update failure

For each page:
- persist concise, actionable error information where possible
- mark page as ocr_failed when safely recordable
- do not mark it ocr_complete unless all required outputs are committed
- continue with other eligible pages
- preserve already completed pages and artifacts
- do not automatically retry indefinitely

Distinguish OCR failures from orchestration or persistence failures in logs and error metadata.

If SQLite becomes unavailable, do not pretend the page status was successfully persisted. Stop or pause safely and surface the infrastructure failure.

---

## Retry semantics

Support explicit retry of failed OCR pages through the existing queue/repository interface.

Retry must:
1. validate that the page is eligible for retry
2. create a new attempt or run directory
3. preserve prior attempt artifacts and errors
4. re-enqueue the page transactionally
5. reset only the fields appropriate for a new attempt
6. avoid duplicate active queue entries
7. leave successful pages untouched

Do not silently retry ocr_complete pages.

If Phase 2 already defines automatic retry policy, honor it. Otherwise implement explicit retry only.

---

## Job lifecycle and progress

Use the established page states:

- queued
- ocr_running
- ocr_complete
- ocr_failed

Retry flow:
- ocr_failed -> queued

Maintain parent job states according to the current project rules.

Progress must be based on persisted page records, not in-memory counters.

Requirements:
- completed pages stay accessible while later pages process
- one page failure cannot erase progress
- parent counts remain consistent after retries
- a job is not considered complete while eligible pages remain queued or running
- reopening the app does not lose queued or completed records

Do not implement notes-related transitions in this phase beyond keeping compatibility with the existing state model.

---

## Concurrency

For this phase:
- OCR worker concurrency remains 1
- only one page may be actively OCR-processed at a time
- queue claims must be atomic and duplicate-safe
- do not parallelize OCR across pages
- keep the design compatible with a future notes queue, but do not implement that queue now

---

## Configuration

Use the existing application config where possible.

Support or verify:
- OCR worker concurrency (default 1)
- output root
- page artifact directory layout
- startup recovery behavior
- explicit retry policy
- whether orchestration starts automatically or is started through a service call

Validate configuration on startup. Reject unsupported concurrency settings rather than silently ignoring them.

Do not add AI provider credentials or notes configuration.

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

Use existing APIs and naming conventions if available.

The service must not require a frontend to function.

Shutdown behavior:
- stop accepting new work
- allow the active page to finish when practical
- if graceful completion is interrupted, rely on the documented startup recovery policy

---

## Testing requirements

Use the existing test framework; prefer unittest when no framework is already established.

Create tests using mocked OCR adapters, temporary directories, and temporary SQLite databases.

Required tests:
1. Multiple pages processed independently.
2. FIFO ordering preserved.
3. Only one OCR page active at a time.
4. Each page receives a unique artifact directory.
5. OCR output and hashes are persisted.
6. Failed page does not stop subsequent pages.
7. Missing/corrupt images fail only their own page.
8. Artifact-write failure does not falsely mark page complete.
9. Explicit retry creates a new attempt without deleting prior artifacts.
10. Completed pages are not reprocessed accidentally.
11. Parent job status and counts remain correct.
12. Restart preserves queued and completed pages.
13. Interrupted ocr_running work follows configured recovery policy.
14. Duplicate queue claims are prevented.
15. Shutdown behavior does not corrupt page state.
16. Existing OCR baseline tests remain unchanged and pass.

If available, add one controlled integration test using the exact configured Python interpreter and installed OCR environment.

Do not invent accuracy results. Historical CER/WER figures remain historical and unreproduced unless independently rerun.

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

Include job ID, page number, attempt count, elapsed time, and error category where available.

Do not log API secrets or expose full local paths unnecessarily.

---

## Deliverables

After implementation, the agent must report:
1. existing architecture discovered
2. files created or modified
3. orchestrator and worker lifecycle
4. artifact layout and immutability guarantees
5. failure and retry semantics
6. configuration changes
7. tests run and actual results
8. unresolved limitations

Do not claim tests passed unless they were actually executed.

---

## Final continuation prompt for the next AI agent

```text
Implement Phase 3: OCR orchestration only.

Context:
- The OCR baseline already exists in this repo and is the source of truth.
- This phase must not implement AI notes generation, provider registry, SSE, or frontend UI.
- Keep the verified OCR environment unchanged.
- Runtime pins remain: Python 3.12.10, PaddleOCR 3.7.0, PaddleX 3.7.2, PaddlePaddle 3.3.1, NumPy 2.3.5, OpenCV 4.10.0, OMP_NUM_THREADS=1.
- requested_engine must remain null.

Scope:
- Build reliable page-by-page OCR orchestration using the existing queue/job/page model and OCR adapter.
- Use the existing OCR adapter contract rather than recreating models.
- Each page is processed independently.
- Each page gets its own artifact output directory.
- Store immutable raw OCR output and related metadata.
- Support retry and failure isolation without stopping other pages.

Requirements:
1. Atomically claim the next eligible page.
2. Mark page as ocr_running with attempt tracking.
3. Validate image source and run OCR for that page only.
4. Write page artifacts to a unique output directory.
5. Verify required outputs were written successfully.
6. Compute hashes for raw OCR and relevant artifacts.
7. Mark the page ocr_complete only after successful artifact commit.
8. Recalculate parent job state and counts transactionally.
9. Continue processing other queued pages without blocking on failures.
10. Keep OCR output immutable; do not rewrite or correct OCR text.
11. Preserve existing runtime and adapter version guards.
12. Support explicit retry of ocr_failed pages without reprocessing successful pages.
13. Validate configuration, concurrency, recovery behavior, and queue semantics.
14. Use unittest style tests with temp DBs and mocked OCR adapters.

Do not:
- implement AI notes, provider registry, or SSE in this phase
- add LLM correction or UI
- change the OCR runtime or model selection
- invent confidence or engine values
- silently fall back to another OCR backend
- overwrite raw OCR or mutate prior artifacts

Deliverables:
- orchestration code
- queue/job/page state handling
- artifact persistence and retry/failure semantics
- tests covering page independence, retry, failure isolation, and job state integrity
- a concise report of what was implemented and what was verified
```

---

## Final instruction summary

This phase is not a rewrite of the OCR system. It is the orchestration layer around the existing OCR baseline.

The next coding agent must protect the baseline, process OCR one page at a time, persist immutable artifacts, and isolate failures without blowing up the whole job.

Everything beyond OCR orchestration remains deliberately out of scope for this phase.
