# Continue Coding Agent Guide

## Purpose of this document

This is the continuation spec for the **next implementation phase**.

Phase 1 (OCR baseline) is already implemented and verified. Do **not** rebuild it. Phase 2 adds an end-to-end **handwritten notes application**:

1. Run OCR on each page.
2. As soon as a page writes `raw.txt`, start an **external AI notes call** for that page.
3. Continue OCR on the next page **in parallel** with the AI call.
4. Show results **page by page** in a UI as Markdown notes.
5. Keep AI providers **configurable from the UI** so free or local models can be added without code changes.

Raw OCR stays immutable. AI cleanup lives in a separate notes stage.

---

## Current project progress (observed facts)

Treat this as the starting state. Do not revert it.

### What already exists

- Package `handwritten_ocr` with CLI: `doctor`, `run`.
- Config: `config/baseline.yaml`.
- Schemas: `schemas/run_result.schema.json`.
- Tests under `tests/` (`unittest` only).
- Sample images: `data/*.png` (59 pages).
- Latest successful batch OCR run:

`outputs/run-20260919T021249Z-012e7ef8dba7`

- Example older page used as the notes-pipeline input contract:

`outputs/run-20260918T201748Z-a4d5d765b86b/documents/a01-003u-26039fabfa22/raw.txt`

### Verified OCR runtime (must remain unchanged)

- Python 3.12.10
- PaddleOCR 3.7.0
- PaddleX 3.7.2
- PaddlePaddle 3.3.1
- NumPy 2.3.5
- OpenCV 4.10.0
- `OMP_NUM_THREADS=1`
- Models: `PP-OCRv6_medium_det`, `PP-OCRv6_medium_rec`
- `runtime.requested_engine: null` (never infer a resolved engine)
- Document-level optional preprocessing disabled; model preprocessing is PaddleX-managed
- Detector request: `limit_side_len=960`, `limit_type=max`, `max_side_limit=4000`, `thresh=0.3`, `box_thresh=0.6`, `unclip_ratio=1.5`
- OCR `correction.status` remains `"skipped"` with an empty audit

**Why 960/max is required:** PaddleX OCR YAML defaults (`limit_side_len=64`, `limit_type=min`) keep full ~2480px pages and caused a Windows access violation in `PaddleStaticRunner`. The requested 960/max path is what the successful 59-page run used.

### OCR artifact contract (do not change)

Each run directory:

```
outputs/run-<utc>-<confighash>/
  run_manifest.json
  documents/<document-id>/
    document.json
    raw.txt          # immutable OCR text; this is the AI trigger
    overlay.png
    crops/line-XXXX.png
```

`raw.txt` is reading-order raw recognition text, including artifacts such as trailing `Name:` and substitution noise (`Labaur`, `nesolution`, `Hause of Loras`). That noise is expected. The AI notes stage must consume it, not rewrite the file.

Example (a01-003u):

```text
Though they may gathe same Left - wing
suppart, a large majority af Labaur
MP. are linely to turn down the Foot-
Griffitus nesolution. Mr. Fodts hine will
...
Name:
```

The notes product for that page is a **new** `notes.md` (and structured JSON), never a mutated `raw.txt`.

---

## Backend fields the notes AI must receive

Source of truth for this section: `outputs/run-20260918T201345Z-a4d5d765b86b` (document `a01-000u-f1764d425a84`). That run shows every field the OCR backend already extracts. The notes stage must use these fields, not only `raw.txt`.

Do **not** send machine-specific paths, `python_executable`, or Windows usernames to the model. Do **not** send evaluation ground-truth to production notes calls (that is lab-only).

### Always send (page payload)

These fields exist on every successful page and are the minimum instruction context:

| Field | Where | Why the model needs it |
| --- | --- | --- |
| `document_id` | `document.json` | Stable page identity in notes.md front matter |
| `source_image` | `document.json` | Human-readable page name |
| `source_image_sha256` | `document.json` | Trace notes back to the exact image |
| `status` | `document.json` | Skip notes if not `success` |
| `image_metadata.width` / `height` / `channels` | `document.json` | Layout context (full page vs snippet) |
| `document_text_raw` and file `raw.txt` | same text | Canonical reading-order page text |
| `regions[]` in **`sorted_index` order** | `document.json` | Line-level repair, not a blob |
| `regions[].region_id` | e.g. `line-0000` | Cite lines in Uncertain readings |
| `regions[].sorted_index` | reading order | Join lines top-to-bottom; ignore `recognition_order` for prose |
| `regions[].detector_index` | detector sequence | Provenance only; not reading order |
| `regions[].raw_text` | per line | Unit of OCR noise to repair |
| `regions[].detector_score` | 0–1 or `null` | Low box score → line may be a false region or form label |
| `regions[].recognition_score` | 0–1 or `null` | Low rec score → prioritize repair; high score can still be wrong (`Name:` ≈ 1.0) |
| `regions[].crop_provenance.status` | `saved` / `invalid_crop` / `invalid_polygon` | Skip invalid lines |
| `correction.status` | always `skipped` in baseline | Model must not assume OCR already cleaned the line |
| `errors[]` | page-level | If non-empty, notes should say OCR was partial |

### Send scores with explicit meaning (direction for the model)

From this run, observed line scores (reading order):

| `sorted_index` | `region_id` | `raw_text` | `detector_score` | `recognition_score` | `recognition_order` |
| --- | --- | --- | --- | --- | --- |
| 0 | line-0000 | A MovE to stop Mr. Gaitskell from | 0.764 | 0.966 | 1 |
| 1 | line-0001 | nominating any mone Labour life Peers | 0.728 | 0.944 | 2 |
| 2 | line-0002 | is to be made at a meeting af Labaur | 0.784 | 0.958 | 7 |
| 3 | line-0003 | MPs domorrow. Mr. Michael Foot has | 0.798 | 0.984 | 4 |
| 4 | line-0004 | put down a vesolution on the subjeat | 0.722 | 0.952 | 3 |
| 5 | line-0005 | and he is do be bached by Mr. Will | 0.794 | 0.957 | 5 |
| 6 | line-0006 | Griffiths, HP for Manchesde Exdlhange. | 0.768 | **0.883** | 6 |
| 7 | line-0007 | Name: | **0.886** | **0.9999** | 0 |

Rules to encode in the system prompt:

- **`sorted_index`** is the only reading order. `recognition_order` is PaddleX crop-batch identity (here `Name:` was recognized first because it is a short/wide crop). Never reorder notes by `recognition_order`.
- **`recognition_score` is mean CTC confidence, not correctness.** `Name:` scored ~1.0 and is still a printed form label to exclude from study notes. `Manchesde Exdlhange` scored lowest (0.883) and should be flagged first.
- **`detector_score` is box confidence, not text quality.** A high detector score on a tiny bottom box often means a form field (`Name:`), not body text.
- Treat **recognition_score &lt; 0.93** as “inspect first”. Treat lines matching `/^Name:\s*$/` (and similar form labels) as **boilerplate**, regardless of score.
- `detector_score` / `recognition_score` may be `null`. Then say “score unavailable”; do not invent 0 or 1.

### Send optionally (helpful, not required for every token)

| Field | Use |
| --- | --- |
| `sorted_polygon` | Vertical position: last box near the bottom of `height` is often a form footer |
| `crop_path` | UI only (show crop next to a flagged line); do not require the model to see pixels in v1 |
| `pipeline_metadata.ordering` | Confirm SortQuadBoxes reading order |
| `timing.detection_ms` / `recognition_ms` | UI elapsed copy only; do not send to the model |

### Never send to the notes model

| Field | Reason |
| --- | --- |
| `evaluation.*` including `reference_text`, CER, WER | Lab-only. Sending GT would leak answers and is unavailable on 58/59 pages |
| `python_executable` and absolute Windows paths | Machine-specific |
| `generated_engine_config` / runner class names | Irrelevant to notes |
| `document_text_corrected` | Always `null` in baseline; do not pretend it exists |

### Compact JSON the orchestrator should POST (example shape)

```json
{
  "document_id": "a01-000u-f1764d425a84",
  "source_image": "a01-000u.png",
  "page_status": "success",
  "image": {"width": 2464, "height": 2480},
  "document_text_raw": "A MovE to stop Mr. Gaitskell from\n...",
  "form_label_hint": "trailing line 'Name:' is a printed form field, not body text",
  "lines": [
    {
      "region_id": "line-0006",
      "sorted_index": 6,
      "raw_text": "Griffiths, HP for Manchesde Exdlhange.",
      "detector_score": 0.768,
      "recognition_score": 0.883,
      "crop_status": "saved",
      "near_bottom": true
    }
  ]
}
```

Omit `recognition_order` from the model payload (keep it in `notes.json` audit if needed). Sort `lines` by `sorted_index` before the call.

---

## Direction prompt (use this system prompt)

Store as `config/notes_prompt.md` (or equivalent) so the UI can edit it later. Default text:

```text
You convert one page of handwritten OCR into clean study notes in Markdown.

You receive JSON with:
- document_text_raw: full page text in reading order (also saved as raw.txt; never ask to change that file)
- lines[]: each OCR line with region_id, sorted_index, raw_text, detector_score, recognition_score, crop_status
- image width/height and a form_label_hint when present

Hard rules:
1. Reading order is sorted_index only (0,1,2,...). Ignore any recognition_order if you see it.
2. detector_score is how confident the detector was that a box is text. recognition_score is CTC confidence for the transcription. Neither score means the spelling is correct.
3. Prefer repairing lines with the lowest recognition_score first. High recognition_score can still be a form label (e.g. "Name:" ~ 1.0).
4. Do not invent facts that are not supported by the lines. If a name or place is garbled, give the most likely English repair and list it under Uncertain readings.
5. Drop printed form leftovers such as a trailing "Name:" from the notes body. Mention them once under Boilerplate omitted.
6. Keep OCR correction status skipped: you produce notes.md only. You do not overwrite raw.txt or region raw_text.
7. Output Markdown only, using this skeleton:

# <short title from the page topic>

## Summary
2–4 sentences of cleaned, grammatical English.

## Notes
- Bullet points in reading order, merging wrapped lines into complete thoughts.

## Uncertain readings
- `OCR token` → likely `repair` (region_id, recognition_score) — reason

## Boilerplate omitted
- e.g. form field `Name:` (region_id)

If crop_status is not saved, skip that line in Notes and mention it under Uncertain readings.
If page_status is not success, say the page is incomplete and only summarize available lines.
```

Worked expectation from this run’s raw lines: `mone`→`more`, `Labaur`→`Labour`, `domorrow`→`tomorrow`, `vesolution`→`resolution`, `subjeat`→`subject`, `bached`→`backed`, `HP`→`MP`, `Manchesde Exdlhange`→`Manchester Exchange`, omit `Name:`. Those repairs are **illustrative** of the harmonic pattern; do not hard-code them as the only dictionary.

---

## Primary objective (phase 2)

Build a notes application on top of the existing OCR package:

- Upload or select page images.
- Process **one page at a time** through OCR.
- When that page’s `raw.txt` is written, **immediately** enqueue an external AI call.
- Start OCR on page N+1 while page N’s AI call is in flight.
- Render each page in the UI as soon as notes Markdown arrives.
- If OCR or AI on a later page is slow, keep the UI engaging with honest per-page status, not a single blocking spinner.

---

## Non-negotiable constraints

1. Do not replace, upgrade, or reinstall the pinned OCR ML environment.
2. Do not put LLM logic inside `handwritten_ocr/correction.py`. OCR correction stays skipped.
3. Do not overwrite `raw.txt`, region `raw_text`, overlays, or crops.
4. Do not hard-code Windows usernames or machine-specific paths.
5. Do not hard-code a single AI vendor in application logic. Providers are data/config.
6. Do not wait for the full document batch before starting AI or UI updates.
7. Do not invent OCR scores, timings, engines, or ground-truth labels.
8. Keep OCR tests on `unittest`. App/API tests may use `unittest` as well; do not require pytest for the OCR package.
9. Secrets (API keys) stay in environment variables or a local untracked file. Never commit keys.
10. Fail closed: if a provider is misconfigured, show a clear page-level error and continue other pages.

---

## Target architecture

Keep OCR as a library. Add a thin orchestration layer and a UI.

Recommended layout (extend in place; do not move the OCR package):

```
handwritten_ocr/          # existing baseline — leave as the OCR engine
notes_app/
  __init__.py
  config.py               # load notes + provider registry
  providers/
    base.py               # NotesProvider protocol
    registry.py           # load providers from YAML / user registry
    openai_compatible.py  # OpenAI-style chat completions
    ollama.py             # local / free OpenAI-compatible servers
  pipeline.py             # page worker: OCR then enqueue notes
  events.py               # SSE/websocket event types
  store.py                # job/page state
  server.py               # HTTP API
web/                      # frontend
config/notes.yaml         # default notes + provider registry
config/providers.example.yaml
outputs/.../documents/<id>/notes.md
outputs/.../documents/<id>/notes.json
```

CLI may grow a `notes` command later. First deliverable is: **API + UI that call existing OCR per page**.

### Processing flow (required)

```
queue = [page1, page2, page3, ...]

for each page:
  1. UI: page status = "ocr_running"  (skeleton / pulse card)
  2. OCR that page only → write document dir + raw.txt
  3. Emit event page.ocr_complete
  4. UI: show raw OCR in a secondary panel (collapsed by default)
  5. Enqueue AI notes job (do not block OCR loop)
  6. UI: page status = "notes_running"  (markdown placeholder, typing/shimmer)
  7. Immediately start OCR on the next page (step 1)

AI worker (parallel, limited concurrency):
  - POST raw.txt (+ optional region list) to selected provider
  - Write notes.md + notes.json beside raw.txt
  - Emit page.notes_complete or page.notes_failed
  - UI replaces placeholder with rendered Markdown
```

OCR is typically slower than a short notes call, but **either stage can stall**. The UI must stay useful when:

- page 1 notes are ready and page 2 OCR is still running
- page 2 OCR finished quickly but the AI provider is slow
- one page fails and later pages succeed

Use a bounded worker pool (default: OCR concurrency **1** because Paddle CPU inference is heavy and previously crashed under oversized inputs; notes concurrency **2** unless the provider rate-limits).

---

## AI notes stage

### Trigger

Trigger on filesystem/API confirmation that `raw.txt` exists and is non-empty for that `document_id`. Watchers are optional; the pipeline should call notes directly after `write_document_artifacts` returns.

Do not poll the whole `outputs/` tree as the primary mechanism. Orchestration already knows the path.

### Input to the model

Build the compact JSON described in **Backend fields the notes AI must receive**. Always include `document_text_raw` plus `lines[]` with `region_id`, `sorted_index`, `raw_text`, `detector_score`, `recognition_score`, and `crop_status`. Sort lines by `sorted_index`. Do not send evaluation/ground truth, absolute paths, or `recognition_order` as reading order.

Use the **Direction prompt** in that section as the system prompt (editable later in the UI).

### Output artifacts (new, next to OCR files)

`notes.md` — presentable Markdown for the UI.

Suggested structure:

```markdown
# <short title inferred from the page>

## Summary
...

## Notes
- ...

## Uncertain readings
- `nesolution` → likely `resolution` (context: parliamentary motion)
```

`notes.json` — machine audit:

```json
{
  "document_id": "...",
  "source_raw_path": "raw.txt",
  "source_raw_sha256": "...",
  "provider_id": "ollama-llama",
  "model": "llama3.2",
  "status": "succeeded",
  "markdown": "...",
  "uncertain_readings": [{"from": "Labaur", "to": "Labour", "confidence": "likely"}],
  "provider_request_id": null,
  "error": null
}
```

If the provider is unavailable, still write `notes.json` with `status: "failed"` and `error`. Do not leave the page spinning forever without a terminal state.

### Prompt policy

Follow the stored direction prompt. Scores guide attention; they do not prove correctness. Form labels with high scores still get omitted from the notes body.

---

## Configurable AI providers (UI + YAML)

Providers must be a **registry**, not `if openai: ... elif groq:` scattered through the pipeline.

### Registry file

`config/providers.yaml` (create from example; gitignore local secrets):

```yaml
providers:
  - id: ollama-local
    label: Ollama (local, free)
    protocol: openai_compatible
    enabled: true
    base_url: http://127.0.0.1:11434/v1
    model: llama3.2
    api_key_env: null
    timeout_s: 120
    max_tokens: 1200

  - id: groq-free
    label: Groq
    protocol: openai_compatible
    enabled: false
    base_url: https://api.groq.com/openai/v1
    model: llama-3.1-8b-instant
    api_key_env: GROQ_API_KEY
    timeout_s: 60
    max_tokens: 1200

  - id: openai-compatible-custom
    label: Custom OpenAI-compatible
    protocol: openai_compatible
    enabled: false
    base_url: ""
    model: ""
    api_key_env: NOTES_API_KEY
    timeout_s: 60
    max_tokens: 1200
```

`config/notes.yaml`:

```yaml
default_provider_id: ollama-local
ocr_concurrency: 1
notes_concurrency: 2
```

### Protocol

Implement **one** HTTP adapter first: OpenAI-compatible chat completions (`/chat/completions`). That covers Ollama, LM Studio, Groq, Together, OpenRouter, vLLM, and many free tiers.

Adding a new free model later should be:

1. Open the UI **Providers** panel.
2. Fill label, base URL, model name, optional API key env/name.
3. Save → append to registry YAML (or a user `providers.local.yaml` that overrides).
4. Test connection (small ping prompt).
5. Select it as the active provider for the next job.

No new Python class is required for another OpenAI-compatible host.

If a future provider is not OpenAI-compatible, add a new protocol module and register it by `protocol` string. The UI should only enable protocols the backend lists.

### UI for providers

- List saved providers with enabled/disabled toggle.
- “Add provider” form: protocol dropdown (start with `openai_compatible`), base URL, model, API key (write to env or local secret store, never into git).
- “Set as default”.
- Per-job override: user can pick a provider before starting a run.
- Validation errors: missing URL, missing key when `api_key_env` is set, HTTP 401/404 shown as provider errors, not OCR errors.

---

## Frontend: page-by-page presentation

The UI is a **job workspace**, not a dump of finished files.

### Layout

- Left: job queue / page list (thumbnail or filename, status chip).
- Center: selected page — Markdown notes (primary), overlay thumbnail, optional raw OCR accordion.
- Right or top: provider selector + progress of the whole job.
- Bottom or toast: live event stream.

### Per-page status chips (required)

| Status | Meaning | UI |
| --- | --- | --- |
| `queued` | Not started | muted card |
| `ocr_running` | PaddleOCR on this page | skeleton lines + elapsed timer |
| `ocr_failed` | OCR error | error + retry OCR |
| `ocr_complete` | `raw.txt` written | brief flash, then notes state |
| `notes_queued` | Waiting for an AI worker | “Notes waiting…” |
| `notes_running` | External AI call | shimmer Markdown + elapsed timer |
| `notes_failed` | Provider error | error + retry notes (keep raw OCR) |
| `notes_ready` | `notes.md` written | rendered Markdown |

Selecting a page that is still `ocr_running` must not block viewing a previous `notes_ready` page.

### Engaging UI when later pages are slow

When page 1 is ready and page 2 OCR/AI is slow:

- Keep page 1 notes fully readable and scrollable.
- Show a persistent job rail: “Page 2 of N — OCR 0:41” with a determinate bar only if you have a real estimate; otherwise indeterminate + elapsed time.
- Use staggered skeleton cards for remaining pages so the user sees N pages exist.
- Subtle motion (shimmer, not aggressive spinners on the whole screen).
- Copy: “Page 1 notes are ready. Later pages can take about a minute each on CPU OCR.”
- Allow cancel of the remaining queue without deleting finished pages.
- Retry is per page and per stage (OCR vs notes).

When the AI stream is supported by the provider, stream tokens into the Markdown preview. If not, keep the shimmer until the full `notes.md` arrives. Do not fake streaming by inventing text.

### Events (SSE recommended)

```json
{"type": "job.started", "job_id": "...", "page_count": 12}
{"type": "page.ocr_started", "document_id": "...", "index": 0}
{"type": "page.ocr_complete", "document_id": "...", "raw_path": "documents/.../raw.txt"}
{"type": "page.notes_started", "document_id": "...", "provider_id": "..."}
{"type": "page.notes_delta", "document_id": "...", "text": "..."}  // optional
{"type": "page.notes_complete", "document_id": "..."}
{"type": "page.failed", "document_id": "...", "stage": "ocr"|"notes", "error": "..."}
{"type": "job.finished", "job_id": "..."}
```

Frontend reduces these into page state. Out-of-order events must be safe (ignore stale `ocr_running` after `notes_ready`).

---

## API sketch

Keep paths relative; no machine-specific defaults in config fingerprints.

- `GET /api/health` — OCR runtime doctor summary + provider ping status.
- `GET /api/providers` / `POST /api/providers` / `PATCH /api/providers/{id}` — registry CRUD.
- `POST /api/jobs` — `{ input_paths or upload, provider_id }` → `job_id`.
- `GET /api/jobs/{id}` — full page state.
- `GET /api/jobs/{id}/events` — SSE.
- `GET /api/jobs/{id}/pages/{document_id}/notes.md` — file.
- `POST /api/jobs/{id}/pages/{document_id}/retry-notes`.

Uploads land in a job-scoped input directory, then OCR `run` is invoked **per image** (or a directory walker that yields one path at a time). Do not wait for a full-directory OCR `run` to finish before notes start.

If reusing `handwritten_ocr.cli._run`, extract a **single-document** function first so the app can persist each page immediately. A 59-image blocking `run` is the wrong shape for this UI.

---

## Implementation tasks (in order)

1. Extract `process_one_image(...)` from the OCR CLI so one page can be written without finishing the whole batch.
2. Add `notes_app` provider registry + OpenAI-compatible client.
3. After each successful page write, hash `raw.txt` and call the notes provider; persist `notes.md` / `notes.json`.
4. HTTP API + SSE job orchestrator (OCR concurrency 1, notes concurrency 2).
5. Frontend job workspace with per-page statuses, Markdown render, provider admin, slow-page engagement states.
6. Tests:
   - OCR regression: `python -m unittest discover -v`
   - Notes: mock HTTP provider; assert `raw.txt` unchanged and `notes.md` created
   - Orchestrator: page2 OCR starts while page1 notes is still in-flight (use fakes)
   - UI: not optional for the happy path — verify page1 visible while page2 is `ocr_running`

---

## Must-not-do list

- Do not rewrite `raw.txt`.
- Do not fold AI output into OCR `correction` records as `"applied"` in the baseline OCR JSON.
- Do not add custom OCR reading-order code.
- Do not compare OCR models in this phase.
- Do not block the UI on the slowest page.
- Do not store API keys in `config/baseline.yaml` or git.
- Do not assume Groq/OpenAI/Ollama is installed; the registry may be empty until the user adds one.

---

## Acceptance bar

Phase 2 is complete when:

- A multi-page upload shows page 1 notes while later pages are still in OCR or AI.
- Each finished page has `raw.txt` (unchanged OCR) and `notes.md` (presentable Markdown).
- A new OpenAI-compatible free model can be added from the UI and used on the next page without a code edit.
- Provider failure fails that page’s notes stage only; OCR artifacts remain.
- Slow later pages show elapsed time / skeleton / “still working” copy, and the user can read finished pages.
- OCR unittest suite still passes.
- `requested_engine` remains null; OCR runtime pins are unchanged.

---

## Ready-to-use continuation prompt

Copy this into the next coding agent session:

```text
Implement phase 2 of the handwritten notes app using Guide.md in this workspace.

Context:
- OCR baseline already works. Package handwritten_ocr, config/baseline.yaml, tests/, data/, outputs/.
- Latest OCR batch: outputs/run-20260919T021249Z-012e7ef8dba7 (59/59 success).
- Example raw OCR input: outputs/run-20260918T201748Z-a4d5d765b86b/documents/a01-003u-26039fabfa22/raw.txt
- Do not rebuild OCR. Do not mutate raw.txt. Do not add LLM logic to handwritten_ocr/correction.py.

Runtime pins stay: Python 3.12.10, PaddleOCR 3.7.0, PaddleX 3.7.2, PaddlePaddle 3.3.1, NumPy 2.3.5, OpenCV 4.10.0, OMP_NUM_THREADS=1, requested_engine null, detector 960/max.

Build:
1. Extract single-page OCR processing so each page writes artifacts immediately.
2. notes_app with a YAML/UI provider registry (OpenAI-compatible protocol first: Ollama, Groq, OpenRouter, custom base_url).
3. When raw.txt is written, call the selected provider and save notes.md + notes.json beside it.
4. Overlap: OCR page N+1 while notes for page N run.
5. Frontend: page-by-page Markdown, status chips, provider add/select, engaging skeletons/timers when later pages are slow. SSE or equivalent live events.
6. Keep secrets out of git. Fail per-page, not the whole job.

Deliver: working API+UI flow, tests with mocked AI, OCR unittests still green.
```

---

## Final note for the next agent

The OCR baseline is the source of truth for pixels-to-text. The new application is a **notes product** that watches each page complete, calls a user-configurable external model, and presents Markdown without blocking on the rest of the stack. Overlap OCR and AI; keep the UI honest about which page is slow.
