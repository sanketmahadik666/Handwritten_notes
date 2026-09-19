# Executive Summary

We propose creating a **new minimal Python package `handwritten_ocr`** that encapsulates a reproducible end-to-end handwritten-English OCR baseline using the verified PaddleOCR 3.7.0/PaddleX 3.7.2 environment. The package will implement the pipeline exactly as in the installed PaddleOCR, from image loading through detection, sorting, cropping, recognition, CTC decoding, and evaluation. All prior discoveries inform design: *SortQuadBoxes* ordering, *CropByPolys* geometry, DB postprocessing rules, dynamic recognition resizing (H=48, width capped 3200), CTC decoding (blank and duplicate removal), and the *PaddleStaticRunner* engine on CPU.  

- **Runtime fingerprint:** We will explicitly capture the actual engine and model configuration (e.g. engine=`paddle`, runner=`PaddleStaticRunner`, `device=cpu`, `cpu_threads=10`, MKL-DNN and CINN disabled).  
- **CLI:** A `handwritten_ocr` CLI with `doctor` (environment check) and `run` commands.  
- **Config:** A YAML config (e.g. `config.yaml`) pinned to use PP-OCRv6 medium detector/recognizer, CPU, no MKL-DNN, no preprocessing by default. All fields (thresholds, model names, etc.) are explicit.  
- **Data models:** Typed classes (`RunConfig`, `DocumentResult`, `RegionResult`, `EvaluationRecord`, `CorrectionResult`) with JSON schema validation.  
- **PaddleX adapter:** A compatibility layer that introspects the installed PaddleX version (with version check), extracts raw polygons, applies PaddleX’s *SortQuadBoxes* and *CropByPolys(det_box_type="quad")* routines, and invokes the actual PaddleX recognition model. This adapter will handle version differences and use only public attributes.  

All claims are backed by our source analysis. For example, the default DB postprocessing uses `thresh=0.3`, `box_thresh=0.6`, `unclip_ratio=2.0`; *SortQuadBoxes* (used for general OCR) sorts by minimum y then x if close vertically; *CropByPolys* uses OpenCV’s `minAreaRect`, `boxPoints`, `warpPerspective` (with cubic interpolation and border replicate) to extract straightened line images; and recognition uses a height of 48px with aspect-ratio resizing, normalization `(x/255 - 0.5)/0.5`, and zero-padding. CTC decoding selects the max-probability class at each timestep, drops blanks (index 0) and repeats, then joins the characters; the recognition score is the mean of the selected timestep probabilities.  The engine resolution trace and live inspection confirm we run **Paddle Static runner on CPU** by default.  

## Project Structure and Required Modules

We will create a new repository with a structure such as:

```
handwritten_ocr/
├── handwritten_ocr/            # Main package
│   ├── __init__.py
│   ├── cli.py                  # CLI entrypoint
│   ├── config.py               # Default configuration and YAML parser
│   ├── pipeline.py             # High-level pipeline orchestration
│   ├── adapters/
│   │   └── paddlex_adapter.py   # Version-gated PaddleX compatibility layer
│   ├── data_models.py          # RunConfig, DocumentResult, RegionResult, EvaluationRecord, CorrectionResult classes
│   ├── utils.py                # Utility functions (logging, geometry, etc.)
│   ├── schemas/                
│   │   └── output_schema.json   # JSON schema for output manifest
│   └── tests/                  
│       ├── test_input.py       # Image loading tests
│       ├── test_pipeline.py    # Pipeline edge case tests (empty, invalid)
│       ├── test_evaluation.py  # CER/WER tests
│       └── ...                 
├── configs/
│   └── baseline.yaml          # Baseline YAML config (pinned models, params)
├── data/                      # (Optional) For integration tests: sample inputs, GT
│   ├── input/                 
│   └── ground_truth/         
├── outputs/                   # Example outputs, overlays, etc.
├── scripts/
│   └── run_ocr.py            # Example usage script (calls CLI)
└── README.md
```

**Key modules:** 
- `cli.py` implements CLI commands: `doctor` and `run`. 
- `pipeline.py` constructs a `HandwrittenOcrEngine` using `RunConfig`, invokes detection, sorting, cropping, recognition, and evaluation, and assembles results. 
- `paddlex_adapter.py` handles version-specific PaddleX calls: locating the internal pipeline object, retrieving model artifacts, and performing detection+cropping via PaddleX. 
- `data_models.py` defines all output record classes with `@dataclass` or pydantic (if allowed) for type checking, plus methods to serialize to JSON with the required schema. 
- `config.py` reads YAML (with `ruamel.yaml` or stdlib `yaml`), applies defaults, and validates fields. 
- `utils.py` may include image I/O, geometric transforms (alpha handling, BGR conversion, region sorting if needed externally), logging setup, etc.  

Each directory and file should be documented. All required Python packages are PaddleOCR (includes paddlex) and standard libraries; we will not add heavy dependencies. The `requirements.txt` pins `paddleocr==3.7.0`, ensuring the exact environment.

## CLI Commands

We provide a `handwritten_ocr` entrypoint exposing at least two subcommands:

- `handwritten_ocr doctor` – Checks environment and models. It will verify:
  - Python version (must be 3.12.10) and `paddleocr` package version (3.7.0).
  - Existence of the PP-OCRv6_medium detector/recognizer model directories (`~/.paddlex/official_models/...` or `--model-dir` overrides).
  - That the model artifacts match PaddleStatic (e.g. presence of `inference.pdmodel` files and no ONNX or `transformers` files). 
  - That MKL-DNN (`enable_mkldnn`) and CINN (`enable_cinn`) are effectively disabled. 
  - That the adapter can locate `ocr.paddlex_pipeline._pipeline` without error.  
  It prints a concise report of “OK” or errors with references to the runtime fields found (engine, runner, model names).

- `handwritten_ocr run --input INPUT [--config CONFIG] [--output-root ROOT] [--ground-truth GTFILE]` – Runs OCR on given image file or directory. 
  - INPUT: file or dir of images.
  - CONFIG: path to YAML config (defaults to `configs/baseline.yaml`).
  - OUTPUT-ROOT: root directory to write outputs (overlaid images, crops, JSON, text).
  - GROUND-TRUTH: optional text file (or directory mapping) for evaluation.  

This command:
  1. Parses `RunConfig` from the YAML (including model names, thresholds, MKL flag, etc.).  
  2. For each image, loads it, records metadata (format, dimensions, channels).  
  3. Invokes the PaddleX detector through the adapter to get raw polygons and confidences (if available; else `null`).  
  4. Applies *SortQuadBoxes* to order regions (maintaining an internal `region_id` stable across steps).  
  5. Uses *CropByPolys(det_box_type="quad")* to extract line crops from the image.  
  6. Feeds all crops to the recognizer (with dynamic resizing to height=48, max width=3200, normalization and padding).  
  7. Applies CTC decoding on the batch output (remove blanks/duplicates, join) and compute `rec_score` as mean probability.  
  8. Reorders the recognized lines according to reading order and assembles `document_text_raw`.  
  9. Optionally evaluates CER/WER against provided ground truth (using total-edit-rate method, see below).  
  10. Writes all results: per-region info (ID, original poly, sorted index, raw text, score, etc.) and document-level info into a JSON. Also save plain-text output and visual overlays (polygons on original image, each crop image with ID).  

All operations must catch and log errors (e.g. unreadable images, degenerate polys) without crashing the entire run.

Example usage:  
```bash
handwritten_ocr doctor
handwritten_ocr run --input data/input_images --config configs/baseline.yaml --output-root outputs/run1 --ground-truth data/gt_a01-000u.txt
```  

## YAML Configuration Fields (baseline.yaml)

The baseline YAML config explicitly mirrors PaddleOCR/PaddleX settings. Required sections:

- **pipeline**:
  - `lang`: `"en"`
  - `enable_mkldnn`: `False`
  - `use_doc_orientation_classify`: `False`
  - `use_doc_unwarping`: `False`
  - `use_textline_orientation`: `False`
  - *Rationale:* Match the user’s environment exactly; disabling optional preproc.

- **detector**:
  - `model_name`: `"PP-OCRv6_medium_det"`
  - `limit_side_len`, `limit_type`, `max_side_limit` (if used; from PaddleX defaults, e.g. 960, "max", 4000).
  - `thresh`: `0.3`
  - `box_thresh`: `0.6`
  - `unclip_ratio`: `2.0`
  - `det_db_unclip_type`: `"avg_score"` (if relevant to DBPostProcess; default).
  - `max_candidates`: `1000`
  - `score_mode`: `"fast"`
  - `box_type`: `"quad"`
  - *Rationale:* These match the default pipeline parameters and ensure correct DB postprocessing.

- **recognizer**:
  - `model_name`: `"PP-OCRv6_medium_rec"`
  - `input_shape`: `null`  (we want dynamic input, not fixed).
  - `score_thresh`: `0` (we use all outputs, filtering done by code as needed).
  - `batch_size`: `1` (for simplicity, or any number; we'll pad in code).
  - *Rationale:* Using dynamic resizing (height=48) rather than fixed, since default `input_shape=None` path was confirmed in code.

- **logging** (optional):
  - `level`: `"INFO"` or `"DEBUG"` for verbose diagnostics.
  - `log_file`: path or null.

- **output**:
  - `save_crops`: true/false (whether to save line crop images).
  - `save_overlays`: true/false.
  - `manifest_name`: e.g. `"ocr_manifest.json"`.
  - *Rationale:* Make these explicit to control output.

**Defaults:** We will hard-code the baseline to disable all improvements: no deskew, no enhancements. Any augmentation or special crop must be off by default. Explicit boolean flags (and versions) should be in the config.  

All fields in the YAML must be validated (e.g. enums for threshold 0≤thresh≤1). We will provide a JSON schema for config if needed. Unrecognized fields should error out.

## Data Models and JSON Schema

We define data models for output records:

1. **RunConfig** – holds all runtime settings derived from CLI and YAML (includes all detector/recognizer params, device, thread count, etc.). Serialize only necessary fields in metadata.

2. **RegionResult** – one object per detected text line:
   - `region_id` (string, stable unique, e.g. “region-0001”)
   - `detector_index` (int, original order from DBPostProcess)
   - `reading_order_index` (int, after sorting)
   - `polygon` (list of 8 numbers [x0,y0,...,x3,y3] in **original image coordinates**)
   - `raw_text` (string, OCR output)
   - `recognition_score` (float or null)
   - `corrected_text` (string or null)
   - `correction_status` (`"skipped"`/`"applied"`/`"failed"`)
   - `timing_ms` (per-region end-to-end time, optional)

3. **DocumentResult** – per-image or per-document result:
   - `document_id` (filename or custom ID)
   - `source_image` (path or name)
   - `image_metadata`: `{width, height, channels}`
   - `pipeline_metadata`: e.g. `{paddleocr_version, paddlex_version, detector_model, recognizer_model, device}`
   - `regions`: list of `RegionResult`
   - `document_text_raw` (string, concatenation in reading order, with line breaks)
   - `document_text_corrected` (string or null)
   - `evaluation`: `{ground_truth_available: bool, cer: float|null, wer: float|null}`
   - `timing`: e.g. `{total_ms: float}`

4. **CorrectionResult** – if a correction method is applied (for future use), include fields:
   - `method_name`: e.g. `"none"` or model name.
   - `changes`: list of edits `{region_id, original, corrected}` or similar.
   - *We will default to skipping correction, i.e. `status="skipped"` and no changes.*  

5. **EvaluationRecord** (internal, not output JSON): holds ground truth vs OCR text and error counts.

We will provide a JSON Schema (in `schemas/output_schema.json`) that requires these fields. For example, an excerpt:

```json
{
  "type": "object",
  "properties": {
    "document_id": {"type": "string"},
    "source_image": {"type": "string"},
    "image_metadata": {
      "type": "object",
      "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}, "channels": {"type": "integer"}}
    },
    "pipeline_metadata": { /* versions, models */ },
    "regions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "region_id": {"type": "string"},
          "detector_index": {"type": "integer"},
          "reading_order_index": {"type": "integer"},
          "polygon": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 8,
            "maxItems": 8
          },
          "raw_text": {"type": "string"},
          "recognition_score": {"type": ["number", "null"]},
          "corrected_text": {"type": ["string","null"]},
          "correction_status": {"type": "string"},
          "timing_ms": {"type": ["number","null"]}
        },
        "required": ["region_id","detector_index","reading_order_index","polygon","raw_text"]
      }
    },
    "document_text_raw": {"type": "string"},
    "document_text_corrected": {"type": ["string","null"]},
    "evaluation": {
      "type": "object",
      "properties": {
        "ground_truth_available": {"type": "boolean"},
        "cer": {"type": ["number","null"]},
        "wer": {"type": ["number","null"]}
      }
    },
    "timing": {
      "type": "object",
      "properties": {"total_ms": {"type": ["number","null"]}}
    }
  },
  "required": ["document_id","source_image","pipeline_metadata","regions","document_text_raw","evaluation"]
}
```

**Example Output JSON** (simplified):

```json
{
  "document_id": "a01-000u",
  "source_image": "a01-000u.png",
  "image_metadata": {"width": 1800, "height": 2280, "channels": 3},
  "pipeline_metadata": {
    "paddleocr_version": "3.7.0",
    "paddlex_version": "3.7.2",
    "paddlepaddle_version": "3.3.1",
    "detector_model": "PP-OCRv6_medium_det",
    "recognizer_model": "PP-OCRv6_medium_rec",
    "device": "cpu"
  },
  "regions": [
    {
      "region_id": "region-0001",
      "detector_index": 0,
      "reading_order_index": 0,
      "polygon": [100, 150, 500, 160, 500, 200, 100, 190],
      "raw_text": "Example text",
      "recognition_score": 0.98,
      "corrected_text": null,
      "correction_status": "skipped",
      "timing_ms": 15.2
    },
    { ... }
  ],
  "document_text_raw": "Example text\nSecond line\n...",
  "document_text_corrected": null,
  "evaluation": {
    "ground_truth_available": true,
    "cer": 0.0512,
    "wer": 0.2245
  },
  "timing": {"total_ms": 67820.5}
}
```

(Here CER and WER are examples from the original report for `a01-000u`.)

## PaddleX 3.7.2 Compatibility Adapter

The heart of the implementation is an *adapter* that drives the installed PaddleX pipeline without changing it. Key points:

- **Version check:** On import, the adapter verifies `paddleocr.__version__ == "3.7.0"` and `paddlex.__version__ == "3.7.2"`. If not, it warns that compatibility is untested. (We assume versions **must** match the analysis environment; else user must manage.)
  
- **Accessing internals:** From `ocr = PaddleOCR(...)`, we find the pipeline object as `ocr.paddlex_pipeline._pipeline` (our inspection found this attribute) and verify its type is `_OCRPipeline`. If missing, fail. Then we introspect:
  - `det_model = pipeline.text_det_model`
  - `rec_model = pipeline.text_rec_model`
  These fields exist for general OCR pipelines.
  For safety, we try alternative names (e.g. `pipeline.det_model`, etc.) with explicit errors if not found.
  
- **Model directory & artifacts:** We inspect `det_model._model_dir` (or `det_model.model_dir`) to find where the model files are. We record this path in the fingerprint. We expect it to contain `inference.pdmodel`/`.pdiparams` (static). Similarly for `rec_model`.
  
- **Detector invocation:** Use `det_model.predict([cv2_image])` or PaddleX pipeline. However, because we need the raw polygons, we should call PaddleX’s detection model directly or through pipeline:
  
  - Option A: If allowed by API, call `paddleocr` pipeline predict on the image and parse text boxes. But that may skip details.
  - **Preferred**: Use `det_model.predict([img])` (batch of one). This returns something like `[{'points': ..., 'scores': ...}]` (API output). We convert points list to polygon list and scores list. If PaddleX’s object returns a list of `DetResult`, we extract `.points`.
  
- **Sort order:** We then apply `SortQuadBoxes()` ourselves (import from `paddlex.inference.pipelines.components.common.sort_boxes`) on the list of polygons. This was used in the pipeline as above. According to source, **SortQuadBoxes** sorts by the minimum Y of each box, then if two boxes have |Δy|<10, the one with smaller x comes first. (We saw this logic in code but haven’t reproduced it here; we trust PaddleX's implementation.) We can either call `SortQuadBoxes()(polys)` or manually re-implement the spec. We should call the class for fidelity, catching exceptions.

- **Cropping:** Using `CropByPolys(det_box_type="quad")` (the same class used by PaddleX) to generate rotated line images. It handles perspective warping and 90° rotation if needed. We pass the original image array and the sorted polygons. This yields a list of cropped numpy images. We then filter out any empty crops (zero area) *and* discard their corresponding polygons to keep indices aligned.

- **Recognition:** For each crop image, we must apply the same resizing as PaddleX. We can either:
  - Let PaddleX do it: feed the raw crop to `rec_model.predict([crop])` (batch) and trust its internal preprocessor. This is simplest (the original investigation shows PaddleX *has* a built-in preprocessor that pads as needed). If we use `predict`, ensure we pass the correct `input_shape=None` so it uses the dynamic path.
  - Or replicate it manually: resize to height 48, cap width at 3200, normalize. But using PaddleX’s method avoids any discrepancy. We will simply batch all crops (padded by toBatch inside PaddleX) and call one `predict`. After prediction, we use `det_model.rec_processor` or our own code to decode output (or rely on `predict` result format).
  
- **Decoding:** If using PaddleX model output directly, we must decode the softmax output. We can copy the logic from PaddleX’s `CTCLabelDecode.apply`: compute `preds_idx = preds.argmax(...)` and `preds_prob = preds.max(...)`, then remove duplicates and blanks. We have verified this is exactly what PaddleX’s Python decoder does (see [19]).

- **Error Handling:** Each step should catch errors:
  - If detection fails or finds no contours, record zero regions.
  - If `CropByPolys` fails (often due to degenerate poly), log a warning and skip that region.
  - If recognition output is empty, record empty text with score 0.
  - If any exception occurs, we should either fail gracefully (skip that image) or abort with an error message, depending on severity.  

- **PaddleX Version Gating:** The adapter should check a version constant (commit hash or `paddlex.__version__`) and assert compatibility. If the internal APIs (attribute names) have changed, it should raise an explicit error.  

All attribute reads (like `text_det_model`, `text_rec_model`, `runner`, etc.) will use `getattr` safely with fallback or clear error.

## Call Graph

The pipeline call graph (with paddle in parentheses):

1. **Initialization:** `ocr = PaddleOCR(...enable_mkldnn=False, ... use_textline_orientation=False, etc.)` – constructs PaddleX pipeline.
2. **PaddleOCR.create_pipeline** calls PaddleX **_OCRPipeline** constructor.
3. **_OCRPipeline** sets up models and runners: 
   - Calls `self.create_model(text_det_config)` to instantiate `TextDetRunnerPredictor`, using PaddleStaticRunner (because engine=paddle).
   - Calls `self.create_model(text_rec_config)` to instantiate `TextRecRunnerPredictor`, using PaddleStaticRunner.
4. **Detection:** The `TextDetRunnerPredictor` (with PaddleStaticRunner) performs text detection. Internally this uses Paddle Inference or TensorRT on CPU (here CPU). After inference, `DBPostProcess` converts probability map to polygons:
   - Binarize with `thresh`.
   - `cv2.findContours` on the binary map.
   - For each contour, apply `unclip` (expansion by `unclip_ratio`), then `minAreaRect` + `boxPoints`.
   - Filter small boxes, limit candidates by `max_candidates`.
   - Compute score using `box_score_fast` (mean inside polygon) and apply `box_thresh`.
   - Restore coordinates to original image size using stored scale.
   - Output: list of rotated-rectangle polygons (4 points each) in original image coords, plus scores.  
   This matches PaddleOCR’s DBPostProcess behavior.
5. **Sorting:** The 4-point boxes are sorted by *SortQuadBoxes* (since `text_type="general"`). This orders them top-to-bottom, left-to-right for near-equal lines.
6. **Cropping:** For each sorted polygon, `CropByPolys` computes a tight quadrilateral crop: 
   - It uses `cv2.minAreaRect` on the polygon, then `cv2.boxPoints` to get 4 vertices (ensuring a proper rectangle).
   - The vertices are ordered (usually top-left first) and a perspective transform matrix is computed.
   - `cv2.warpPerspective` extracts the straightened crop, with border replication and cubic interpolation.
   - If the crop is “tall” (height/width ≥ 1.5), it rotates the image 90° (so text is horizontal).
7. **Recognition:** The list of crops goes into the recognizer. Either we rely on PaddleX to batch internally, or we individually feed them:
   - Each crop is resized to height=48, width=ceil(48×max(w/h, 320/48)) up to 3200, using OpenCV (preserving aspect ratio).
   - The resized image (H×W) is transposed to CHW, normalized `(x/255 - 0.5)/0.5`.
   - All crops are padded to the same W (max in batch) as needed, then passed through the recognition model (`TextRecRunnerPredictor`).
8. **CTC Decode:** The recognizer outputs a 3D tensor (timesteps × chars). We convert to text:
   - Take `argmax` over chars at each timestep to get indices (including blank=0).
   - Take the corresponding max probabilities.
   - Scan through the sequence: drop blanks and collapse repeats.
   - Map indices to characters via the PaddleOCR char dictionary (id=0 is blank) to form `raw_text`.
   - Compute `rec_score = mean(selected_probs)`.
9. **Assembly:** The raw texts (already in sorted order) are joined with newline separators to form the document text. 
10. **Evaluation (if GT provided):** Compare `document_text_raw` to ground truth (after agreed normalization) to compute CER/WER (see below).

Each pipeline stage’s inputs and outputs:

- **Input Layer:** Files or directory → validated images (RGB/BGR/gray conversion) + file metadata.
- **Detection Stage:** Input: image array. Output: list of polygons + scores (image coords).
- **Sorting Stage:** Input: raw polygons. Output: sorted polygons with consistent region IDs.
- **Cropping Stage:** Input: image + polygons. Output: list of cropped line images + updated polygon mapping.
- **Recognition Preprocess:** Input: list of crop images. Output: padded numpy batch tensor.
- **Recognition Stage:** Input: batch tensor. Output: list of text strings and scores.
- **Decoding Stage:** Input: raw model outputs. Output: final text strings, rec_scores.
- **Assembly Stage:** Input: list of RegionResults. Output: DocumentResult JSON + plain text.
- **Evaluation:** Input: raw OCR text + ground truth. Output: CER/WER metrics in JSON.

All coordinates remain in the **original image’s pixel coordinate frame**. The adapter must invert any pre-sorting index changes. Errors (e.g. failure to detect any box) should not crash; instead produce zero regions and log a warning.

### Pipeline Diagram

```mermaid
graph TD
    A[Input Image(s)] --> B[Load/Validate]
    B --> C{Optional Preprocessing}
    C --> D[Text Detection (PP-OCRv6_det)]
    D --> E[DB Post-Processing (binarize, contours, unclip)]
    E --> F[Raw Polygons (original coords)]
    F --> G[SortQuadBoxes → Ordered Polygons]
    G --> H[CropByPolys (perspective warp) → Line Images]
    H --> I[Recognition Resize + Normalize + Batch Pad]
    I --> J[Text Recognition (PP-OCRv6_rec)]
    J --> K[CTC Decode (argmax, remove blank/dups) → Text + Score]
    K --> L[Regions with raw_text, rec_score]
    L --> M[Reading-Order Assembly → Document Text]
    M --> N[JSON & Text Output]
    N --> O[Evaluation (if GT) → CER/WER]
```

This matches our earlier conceptual pipeline, with actual PaddleX components substituted. 

## Geometric Example

Suppose we have a detected rotated box polygon with points (in image coords): `[(100,150), (500,160), (490,210), (95,200)]`. This might come from DB. 

1. **SortQuadBoxes**: Only one box, so order=0.  
2. **CropByPolys**: `minAreaRect` might produce a rectangle of width≈400, height≈55, angle≈1°. After rounding and ordering points, the transform matrix extracts a ~ (55×400) image. Since height<width, no 90° rotation.  
3. **RecResize**: Original crop is H=55, W=400. `wh_ratio=400/55≈7.27`, `max_wh_ratio=max(320/48=6.67, 7.27)=7.27`, `target_width=ceil(48×7.27)=349`. So we resize the crop to 48×349.  
4. **Normalize**: Pixel values in [0,255] are converted: `(x/255 - 0.5)/0.5`.  
5. **Pad**: If batch max width is higher, pad to that width with zeros on the right. Otherwise, pad to 349 exactly.  
6. **Recognition output** (example): suppose model outputs logits over 5 timesteps. After softmax and argmax, we get `preds_idx = [23, 23, 3, 3, 22]` with `preds_prob = [0.9,0.85,0.8,0.75,0.88]`. Characters 23,3,22 map to say ['a','b','c'] (depending on dict). Remove duplicates/blanks: final `['a','b','c']`. Raw text = `"abc"`, rec_score = mean([0.9,0.8,0.88]) = 0.86.  

This toy example matches the logic in [19].  

## Testing and Validation

**Unit Tests:** Use Python’s `unittest` (no pytest). Key tests:

- **Image Input Validation:** e.g. `test_input.py` cases:
  - Accepts PNG, JPG, rejects unsupported like PDF (expect error).
  - Handles grayscale and BGR images (simulate by loading arrays).
  - Multi-channel handling: If image has alpha, ensure correct behavior (either reject or composite, but record it).

- **Schema Validation:** `test_schema.py`:
  - Serialize a dummy `DocumentResult` and validate with JSON schema. For example, missing required fields should fail.

- **Pipeline Logic:** `test_pipeline.py`:
  - Mock detection output: feed a dummy image to a fake `detector.predict()` returning known polygons, test that sorting, cropping, and region mapping produce correct order and coordinates.
  - Edge cases: empty polygon list (should yield empty regions).
  - Polygons with <4 points (invalid) should be caught/ignored.
  - Overlapping or multi-column: ensure *SortQuadBoxes* yields consistent stable order.

- **Crop/Source Linkage:** `test_crop_mapping.py`:
  - Given a known polygon, verify that the crop’s corners map back to original polygon (inverse transform).
  - That the stored polygon in output equals the input (no rounding error beyond int conversion).

- **Empty Recognition:** `test_recognition.py`:
  - If a crop is blank or too small, ensure it yields empty string with score=0 (not crash).

- **CER/WER Calculations:** `test_evaluation.py`:
  - Known examples: 
    - REF="hello world", HYP="hello world" → CER=0, WER=0.
    - REF="a b", HYP="ab" (space missing) → CER=1/2, WER=1/1.
    - For aggregation: feed multiple lines and verify sum of edits/total char/word.
  - Edge: empty reference or hypothesis (define behavior).

- **Batch vs Single Crop:** `test_batch_behaviour.py`:
  - Feed N small images to rec_model.predict (in batch vs one-by-one) and ensure identical text outputs.
  - (Here we may mock `rec_model` to return fixed outputs to speed testing.)

**Integration Tests:** `tests/integration/` with real data:
- Use the three provided `a01-000u.png`, `a01-003u.png`, `a01-007u.png`.
- Run through `handwritten_ocr run` (possibly with a fixture overriding I/O) and verify:
  - For `a01-000u`, match known CER ~5.12%, WER ~22.45% when compared to the sepcified ground truth (with the prescribed normalization). 
  - Confirm 8 regions detected as reported.
- Ensure images and output files are written in the expected structure.

**Test Commands:** For unittest, user can run:
```bash
python -m unittest discover -v
```
which will run all tests in `handwritten_ocr/tests`. We may also provide a `make test` or similar.

## Output Manifest

We will output a single JSON per document as above, plus a manifest or log summarizing the run. For example:

```json
{
  "timestamp": "2026-09-19T12:34:56Z",
  "args": {
    "input": "data/input",
    "config": "configs/baseline.yaml",
    "ground_truth": "data/gt.txt"
  },
  "environment": {
    "python": "3.12.10",
    "paddleocr": "3.7.0",
    "paddlex": "3.7.2",
    "paddlepaddle": "3.3.1"
  },
  "requested_engine": null,
  "resolved_engine": "paddle",
  "detector": {
    "model": "PP-OCRv6_medium_det",
    "predictor": "TextDetRunnerPredictor",
    "runner": "PaddleStaticRunner",
    "device": "cpu",
    "run_mode": "paddle",
    "threads": 10,
    "model_dir": "/home/user/.paddlex/official_models/PP-OCRv6_medium_det"
  },
  "recognizer": {
    "model": "PP-OCRv6_medium_rec",
    "predictor": "TextRecRunnerPredictor",
    "runner": "PaddleStaticRunner",
    "device": "cpu",
    "run_mode": "paddle",
    "threads": 10,
    "model_dir": "/home/user/.paddlex/official_models/PP-OCRv6_medium_rec"
  },
  "results": [
    {
      "document_id": "a01-000u",
      "status": "success",
      "total_regions": 8,
      "evaluation": {"cer": 0.0512, "wer": 0.2245}
    },
    ...
  ]
}
```

This manifest JSON schema can also be defined. It records the key resolution we made for engines and models (as in [27] and [23]). 

## Experimental Plan & Timeline

**Phase 1 (Days 1–2): Repository Audit and Design.**  
- Inspect current repo: confirm nothing functional should be overwritten. Identify entry points, existing scripts.  
- Finalize module structure and config schema. Document all assumptions.  
- Cite any uncovered details about existing code (none found relevant here, since the plan is to start fresh).

**Phase 2 (Days 2–4): Implement Adapter and Core Pipeline.**  
- Write `paddlex_adapter.py` using introspection (verifying version and attributes). Test that it reproduces the polygon outputs for a sample image (without full run).  
- Implement detection wrapper and cropping, verifying with a known synthetic polygon. (E.g. create a small image with text, ensure polygons and crops are correct.)  
- Write region and document data models, YAML parsing, and JSON schema.  

**Phase 3 (Days 4–6): Recognition and Decoding.**  
- Integrate recognition: either call `rec_model.predict` or incorporate *RecResizeNorm* steps. Test with one crop image that the model returns a plausible string.  
- Implement CTC decoding using code matching [19†L119-L127][19†L129-L135] and verify on known examples (e.g. from the ONNX/Swift code).  
- Ensure rec_score is computed as mean of chosen probs (or 0 if empty).

**Phase 4 (Days 6–7): Integration Runner and Outputs.**  
- Implement `run` command: loop over images, call adapter, assemble outputs, write JSON and text files.  
- Generate overlays: draw polygons and IDs on the original image (OpenCV).  
- Save crop images with stable filenames.

**Phase 5 (Day 8): Evaluation.**  
- Hard-code the ground truth for `a01-000u` (excluding the printed "Name:" label per instructions).  
- Normalize both OCR and GT (NFC, lower-case, collapse whitespace) in a documented way.  
- Compute CER/WER by summing all edits over total chars/words (not per-line average). Verify CER≈0.0512, WER≈0.2245 for `a01-000u`.  
- For `a01-003u`/`007u`, no ground truth, mark `ground_truth_available=false`.  

**Phase 6 (Day 9): Testing.**  
- Write unit tests as outlined. Mock PaddleX calls for some.  
- Run integration test on `a01` set, capturing metrics.  
- Fix any issues.

**Phase 7 (Day 10): Documentation and Final Report.**  
- Assemble architecture diagram (above Mermaid).  
- Write this report, inserting citations to [23], [19], [15], [27] to justify critical design points.  
- Provide final output examples, schema, and running instructions.  

All implementation decisions and code changes will be **source-driven** (using our analysis of PaddleX code) and **evidence-backed**. For example, the sorting and cropping steps are exactly as in the inspected PaddleX code [23][15]. The decoding logic is identical to PaddleOCR’s official CTC rules. We will **not guess** anything unverified. Assumptions (e.g. test data availability, OS permissions) will be documented clearly.

**Milestones:**
- **M1 (Day 2):** Config schema and CLI scaffolding ready.
- **M2 (Day 4):** Detection adapter prototype returns correct polygons.
- **M3 (Day 6):** Recognition and decode integrated.
- **M4 (Day 7):** Full raw-OCR run outputs JSON/text for sample image.
- **M5 (Day 8):** Evaluation on `a01-000u` with correct CER/WER.
- **M6 (Day 9):** All unit tests passing.
- **M7 (Day 10):** Complete report with diagrams and examples.

## References

- PaddleX 3.7 inference pipeline code (SortQuadBoxes, CropByPolys).  
- PaddleOCR 3.7 CTC decoding logic.  
- Det-DB postprocess logic (thresholding, contours).  
- Engine resolution to PaddleStaticRunner.  

These sources ground the design choices above.  

