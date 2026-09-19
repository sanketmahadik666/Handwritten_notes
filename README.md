# Handwritten English OCR Baseline

This project is a reproducible, auditable baseline for handwritten-English OCR.
It preserves the raw PaddleX recognition result exactly, records image and
runtime provenance, and separates optional evaluation from OCR inference.

## Verified runtime and assumptions

The baseline targets the existing Python 3.12.10 environment with PaddleOCR
3.7.0, PaddleX 3.7.2, PaddlePaddle 3.3.1, NumPy 2.3.5, and OpenCV 4.10.0. It
does not install, upgrade, or replace model packages. The requested engine in
`config/baseline.yaml` is intentionally `null`; a generated `paddle_static`
configuration bucket is recorded separately from direct runtime observations.

The default pipeline uses PP-OCRv6 medium detection and recognition models.
Document orientation classification, document unwarping, and text-line
orientation are disabled. This does **not** mean that there is no processing:
PaddleX continues to manage decoding, detector preprocessing, polygon crops,
recognition resizing/padding/normalization/batching, and CTC decoding.

## Commands

Run the compatibility doctor with the verified interpreter:

```powershell
& <python-3.12-path> -m handwritten_ocr doctor --config config/baseline.yaml
```

Run one image or a directory. The input path is supplied at execution time and
is never embedded in the package:

```powershell
& <python-3.12-path> -m handwritten_ocr run `
  --input <image-or-directory> `
  --config config/baseline.yaml `
  --output-root outputs
```

To evaluate only the verified `a01-000u.png` reference, add:

```powershell
--ground-truth config/a01-000u.ground_truth.json
```

Run the fast, mocked unit suite without pytest:

```powershell
& <python-3.12-path> -m unittest discover -v
```

## Provenance and artifacts

Every `run` creates a unique `run-<UTC timestamp>-<config hash>` directory.
It contains `run_manifest.json` and a `documents/<document-id>/` directory per
input image. Each document directory contains:

- `document.json`: schema-validated structured regions, polygons, provenance,
  scores, status, timing, and evaluation.
- `raw.txt`: exact reading-order raw OCR text.
- `overlay.png`: a separate source-coordinate polygon overlay labelled with
  stable region IDs and sorted indices.
- `crops/line-XXXX.png`: PaddleX-generated text-line crops when valid.

Source-file SHA-256 values and a canonical requested-configuration hash make
runs comparable without putting machine-specific absolute paths into the
configuration fingerprint. Runtime manifests distinguish requested engine,
pipeline engine, generated engine configuration, observed predictor/runner
classes, and unavailable values (`null`). A runner class is not treated as an
inferred engine value.

## Raw OCR, ordering, and internal compatibility

The adapter uses the checked PaddleOCR 3.7.0 / PaddleX 3.7.2 internal route to
capture detector `dt_polys` before sorting, invoke PaddleX's own
`_sort_boxes`/`SortQuadBoxes` and `_crop_by_polys`/`CropByPolys`, then call the
PaddleX recognizer. It does not duplicate crop geometry, recognition
preprocessing, CTC decoding, or add a custom reading-order algorithm.

PaddleX may reorder crop inference by aspect ratio. The adapter restores
recognition results using crop identity, never recognised text. These private
attributes are version-sensitive. If versions, object paths, return shapes, or
required fields differ, the command fails with an explicit compatibility error
instead of falling back to a similar implementation.

The baseline accepts only `preprocessing.mode: original` with no additional
operations. Future geometry-changing experiments must persist an invertible
source-to-output transform and restore polygons to source coordinates; the
provided geometry helpers reject non-restorable transforms.

## Evaluation and correction policy

Evaluation is available only for entries explicitly marked `verified` in a
ground-truth JSON manifest. Normalization is NFC, case-sensitive, whitespace
run collapse, and punctuation preservation. It stores raw and normalized text
separately, reports substitution/insertion/deletion counts, and calculates
corpus metrics from total edits over total reference length rather than
averaging document rates.

The `a01-000u` manifest explicitly excludes a trailing printed `Name:` line
from the evaluation hypothesis. The raw OCR output still includes it unchanged.
The supplied `a01-003u` and `a01-007u` files have no verified entry and are
therefore not evaluated.

No production corrector, dictionary, heuristic, language model, or LLM is
included. Every baseline region has `correction.status: "skipped"`, no
corrected text, and an empty change audit.

The historical 5.12% CER and 22.45% WER figures are reference observations
from an earlier implementation, not acceptance targets or reproduced results.
Only metrics emitted by an actual run are measured results.

## Known limitations

- The pipeline intentionally retains PaddleX `SortQuadBoxes` behavior; it does
  not solve multi-column or irregular-layout ordering.
- Detector confidence is recorded only when the installed detector actually
  exposes it; otherwise it is `null` and is never replaced with recognition
  confidence.
- Per-region timing is `null` where PaddleX only exposes a batch-stage timing.
- The adapter is intentionally tied to PaddleOCR 3.7.0 and PaddleX 3.7.2.
