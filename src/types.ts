export interface ProviderModel {
  id: string;
  label: string;
  protocol: string;
  enabled: boolean;
  base_url: string;
  model: string;
  has_api_key: boolean;
  timeout_s?: number;
  max_tokens?: number;
  latency_ms?: number | null;
}

export interface ProviderListResponse {
  default_provider_id: string;
  providers: ProviderModel[];
}

export interface PageStatusModel {
  document_id: string;
  index: number;
  status:
    | 'queued'
    | 'ocr_running'
    | 'ocr_failed'
    | 'ocr_complete'
    | 'notes_queued'
    | 'notes_running'
    | 'notes_failed'
    | 'notes_ready'
    | 'failed';
  raw_sha256?: string | null;
  has_overlay: boolean;
  has_notes: boolean;
  source_image?: string;
  line_count?: number;
  error?: string;
  elapsed_ms?: number;
  retry_count?: number;
  notes_status?: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'completed_with_errors' | 'failed';
  provider_id?: string | null;
  total_pages: number;
  created_at: string;
  pages: PageStatusModel[];
}

export interface OCRRegion {
  region_id: string;
  detector_index: number;
  sorted_index: number;
  raw_polygon: [number, number][];
  sorted_polygon: [number, number][];
  text_rec_score: number;
  detector_score: number | null;
  crop_status: string;
  crop_path?: string;
  raw_text: string;
  normalized_text?: string;
  recognition_order?: number;
  correction?: {
    status: string;
    corrected_text: string | null;
    method: string | null;
    changes: any[];
  };
  crop_provenance?: {
    source_document: string;
    detector_index: number;
    sorted_index: number;
    polygon_coordinate_space: string;
    generation_method: string;
    status: string;
  };
}

export interface DocumentEvaluation {
  ground_truth_available: boolean;
  status: 'evaluated' | 'ground_truth_unavailable' | 'unverified';
  reference_text?: string;
  evaluation_hypothesis_text?: string;
  normalized_reference_text?: string;
  normalized_hypothesis_text?: string;
  exclusion?: {
    status: string;
    reason: string;
    source: string;
    exclude_trailing_raw_lines?: string[];
    excluded_raw_lines?: string[];
  };
  character?: {
    substitutions: number;
    insertions: number;
    deletions: number;
    total_edits: number;
    reference_length: number;
    hypothesis_length: number;
    rate: number;
  };
  word?: {
    substitutions: number;
    insertions: number;
    deletions: number;
    total_edits: number;
    reference_length: number;
    hypothesis_length: number;
    rate: number;
  };
}

export interface DocumentData {
  document_id: string;
  source_image: string;
  source_path: string;
  source_image_sha256?: string;
  image_metadata?: {
    width: number;
    height: number;
    channels: number;
    input_handling?: {
      decoder: string;
      operations: string[];
      decoded_dtype: string;
      model_input_channels: number;
    };
  };
  pipeline_metadata?: {
    paddleocr_version: string;
    paddlex_version: string;
    paddlepaddle_version: string;
    detector_model: string;
    recognizer_model: string;
    detector_device?: string;
    recognizer_device?: string;
    coordinate_space: string;
    ordering: string;
  };
  regions: OCRRegion[];
  document_text_raw?: string;
  document_text_corrected?: string | null;
  evaluation?: DocumentEvaluation;
  timing?: {
    image_load_ms: number;
    detection_ms: number;
    sorting_ms: number;
    cropping_ms: number;
    recognition_ms: number;
    serialization_ms: number;
  };
  status?: string;
  errors?: string[];
}

export interface SSEEventRecord {
  id: string;
  timestamp: string;
  type: string;
  job_id: string;
  data: any;
}

export type SSEConnectionState = 'connected' | 'connecting' | 'reconnecting' | 'disconnected';

export interface SSEBackoffInfo {
  state: SSEConnectionState;
  retryCount: number;
  maxRetries: number;
  nextRetryDelayMs: number | null;
  secondsRemaining: number | null;
  lastConnectedTime: string | null;
  lastErrorTime: string | null;
}

export interface HealthResponse {
  status: string;
  ocr_runtime: {
    paddleocr: string;
    paddlex: string;
    paddlepaddle: string;
    python: string;
    numpy: string;
    opencv: string;
    requested_engine: string | null;
    resolved_engine: string | null;
    omp_num_threads: number;
    device: string;
    cpu_threads: number;
    detector_model: string;
    recognizer_model: string;
    detector_predictor: string;
    recognizer_predictor: string;
  };
  providers: {
    id: string;
    available: boolean;
    latency_ms: number | null;
  }[];
  worker_queue: {
    status: 'idle' | 'busy';
    active_jobs: number;
    queued_pages: number;
    degraded_mode: boolean;
    degraded_reason: string | null;
  };
}

export interface BenchmarkMetrics {
  run_id: string;
  git_commit: string;
  config_sha256: string;
  created_at_utc: string;
  runtime_versions: {
    python: string;
    paddleocr: string;
    paddlex: string;
    paddlepaddle: string;
    numpy: string;
    opencv: string;
    omp_num_threads: string;
  };
  model_names: {
    detector: string;
    recognizer: string;
  };
  predictor_classes: {
    detector: string;
    recognizer: string;
  };
  device: string;
  cpu_threads: number;
  requested_engine: string | null;
  resolved_engine: string | null;
  document_count: number;
  region_count: number;
  success_count: number;
  failure_count: number;
  cer: number;
  wer: number;
  character_accuracy: number;
  exact_line_accuracy: {
    rate: number;
    categories: {
      exact_match: number;
      minor_error: number;
      major_error: number;
      unreadable: number;
      false_detection: number;
      missing_detection: number;
    };
  };
  edit_counts: {
    character: {
      substitutions: number;
      insertions: number;
      deletions: number;
      total_edits: number;
      reference_length: number;
      rate: number;
    };
    word: {
      substitutions: number;
      insertions: number;
      deletions: number;
      total_edits: number;
      reference_length: number;
      rate: number;
    };
  };
  normalization_policy: {
    unicode: string;
    case_sensitive: boolean;
    whitespace: string;
    punctuation: string;
  };
  latency_statistics: {
    image_load_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    detection_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    sorting_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    cropping_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    recognition_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    serialization_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    total_wall_clock_ms: { min: number; mean: number; median: number; p95: number; max: number; std: number };
    cold_start_ms: number;
    warm_run_ms: number;
  };
  throughput: {
    page_throughput: number;
    region_throughput: number;
    character_throughput: number;
    notes: string;
  };
  resource_statistics: {
    cpu_utilization_mean: number;
    cpu_utilization_peak: number;
    cpu_model: string;
    cpu_thread_count: number;
    memory_before_model_load_mb: number;
    memory_after_model_load_mb: number;
    peak_inference_memory_mb: number;
    memory_after_processing_mb: number;
    memory_growth_across_runs_mb: number;
  };
  reliability_statistics: {
    total_runs: number;
    success_count: number;
    failure_count: number;
    cer_variance: number;
    wer_variance: number;
    retry_success_rate: number;
    event_delivery_status: string;
    failure_categories: Record<string, number>;
  };
  ground_truth_status: {
    verified_documents: string[];
    unverified_documents: string[];
    corpus_claim_warning: string;
  };
  identity_mapping: {
    success_rate: number;
    mismatch_count: number;
    critical_case: {
      region: string;
      sorted_index: number;
      recognition_order: number;
      interpretation: string;
    };
  };
  academic_rules_enforced: string[];
}

export interface SampleImageItem {
  name: string;
  path: string;
  has_precomputed: boolean;
  document_id?: string;
  job_id?: string;
}

export interface RunHistoryItem {
  run_id: string;
  created_at_utc: string;
  config_sha256: string;
  git_commit: string;
  document_count: number;
  cer: number | null;
  wer: number | null;
  status: string;
}

export interface CropInfo {
  region_id: string;
  sorted_index: number;
  detector_score: number | null;
  recognition_score: number | null;
  crop_status: string;
  path: string;
}

export interface LineInspectionData {
  region_id: string;
  detector_index: number;
  sorted_index: number;
  recognition_order?: number;
  raw_text: string;
  detector_score: number | null;
  recognition_score: number | null;
  crop_status: string;
  polygon: [number, number][];
  correction_status: string;
  crop_url: string;
}

export interface ProviderTestResult {
  success: boolean;
  latency_ms?: number;
  message?: string;
  error?: string;
}

