// TypeScript models of the FastAPI responses (see API_DOCUMENTATION.md and DATA_DICTIONARY.md).

export type QuantityKind = "measured" | "image_derived" | "calculated" | "predicted" | "simulated";
export type JobState = "queued" | "processing" | "completed" | "failed" | "cancelled";
export type ExperimentStatus = JobState | "draft";
export type DataClass = "user" | "nasa_psi" | "synthetic";

export interface Calibration {
  known_length_mm: number;
  measured_length_px: number;
  measured_length_sigma_px?: number;
  known_length_sigma_mm?: number;
  image_width?: number | null;
  image_height?: number | null;
  camera_id?: string | null;
  lens?: string | null;
  configuration?: string | null;
  method?: string;
  notes?: string;
  mm_per_px?: number;
  mm_per_px_sigma?: number;
  created_at?: string;
}

export interface SegmentationConfig {
  method?: "otsu" | "adaptive" | "fixed" | "hsv" | "background_subtraction";
  channel?: "max" | "gray" | "blue" | "green" | "red";
  blur_kernel?: number;
  threshold_offset?: number;
  fixed_threshold?: number;
  morph_kernel?: number;
  open_iterations?: number;
  close_iterations?: number;
  min_contour_area_px?: number;
  min_contrast?: number;
  min_candidate_contrast?: number;
}

export interface AnalysisConfig {
  segmentation?: SegmentationConfig;
  derivatives?: { window?: number; polyorder?: number; max_gap_factor?: number };
  frame_step?: number;
  max_frames?: number | null;
  start_time_s?: number | null;
  end_time_s?: number | null;
  processing_scale?: number;
  edge_sigma_px?: number;
  radius_method?: "equivalent" | "limb";
  limb_center_hint?: [number, number] | null;
  limb_min_radius_mm?: number | null;
  decoder?: "auto" | "opencv" | "ffmpeg";
  [key: string]: unknown;
}

export interface Experiment {
  id: string;
  name: string;
  description: string;
  data_class: DataClass;
  created_at: string;
  updated_at: string;
  fuel_type: string | null;
  oxygen_fraction: number | null;
  chamber_pressure_kpa: number | null;
  burn_duration_s: number | null;
  camera: Record<string, unknown> | null;
  calibration: Calibration | null;
  analysis_config: AnalysisConfig | null;
  dataset_ref: string | null;
  video_ref: string | null;
  video_filename: string | null;
  status: ExperimentStatus;
  model_version: string | null;
  latest_job_id: string | null;
  archived: boolean;
}

export interface ExperimentCreate {
  name: string;
  description?: string;
  fuel_type?: string | null;
  oxygen_fraction?: number | null;
  chamber_pressure_kpa?: number | null;
  burn_duration_s?: number | null;
  camera?: Record<string, unknown> | null;
  calibration?: Calibration | null;
  analysis_config?: AnalysisConfig | null;
  dataset_ref?: string | null;
}

export interface ValidationIssue { code: string; severity: "info" | "warning" | "error"; message: string; frame_index?: number | null }

export interface Stat { min: number; max: number; mean: number; std: number; n: number }

export interface ExtinctionEstimate {
  status: "observed" | "flame_present_at_end" | "insufficient_trailing_frames" | "never_detected";
  time_s: number | null;
  uncertainty_s: number | null;
  last_detected_time_s: number | null;
  first_missing_time_s: number | null;
  message: string;
}

export interface AnalysisSummary {
  frames_decoded: number;
  frames_analyzed: number;
  status_counts: Record<string, number>;
  detection_rate: number;
  timestamp_source: string;
  analysed_time_span_s: number;
  calibrated: boolean;
  radius_method: "equivalent" | "limb";
  limb_fits_ok: number | null;
  limb_radius_mm: Stat | null;
  limb_radius_px: Stat | null;
  equivalent_radius_px: Stat | null;
  radius_mm: Stat | null;
  peak_radius: { frame_index: number; timestamp_s: number; equivalent_radius_px: number; radius_mm: number | null; radius_sigma_mm: number | null } | null;
  expansion_velocity_px_s: Stat | null;
  expansion_velocity_mm_s: Stat | null;
  circularity: Stat | null;
  frames_volume_suppressed_non_spherical?: number;
  shape_stability_cv: number | null;
  eccentricity: Stat | null;
  boundary_roughness: Stat | null;
  extinction: ExtinctionEstimate;
  processing: { wall_time_s: number; frames_per_second: number | null; realtime_factor: number | null; processing_scale: number; frame_step: number; system: Record<string, unknown> };
  decoder?: string;
  [key: string]: unknown;
}

/** One frame of analysis output (FrameMeasurement). Units per DATA_DICTIONARY.md. */
export interface FlameMeasurement {
  experiment_id: string;
  frame_index: number;
  timestamp_s: number;
  status: "detected" | "low_confidence" | "not_detected" | "rejected_discontinuity" | "frame_error";
  confidence: number;
  segmentation_quality: number;
  contrast: number | null;
  n_candidates: number;
  centroid_x_px: number | null;
  centroid_y_px: number | null;
  enclosing_center_x_px: number | null;
  enclosing_center_y_px: number | null;
  enclosing_radius_px: number | null;
  equivalent_radius_px: number | null;
  equivalent_radius_sigma_px: number | null;
  equivalent_diameter_px: number | null;
  area_px2: number | null;
  perimeter_px: number | null;
  circularity: number | null;
  eccentricity: number | null;
  boundary_roughness: number | null;
  touches_border: boolean | null;
  radius_mm: number | null;
  radius_sigma_mm: number | null;
  diameter_mm: number | null;
  area_mm2: number | null;
  perimeter_mm: number | null;
  equivalent_volume_mm3: number | null;
  equivalent_volume_sigma_mm3: number | null;
  radius_smoothed_px: number | null;
  expansion_velocity_px_s: number | null;
  expansion_velocity_sigma_px_s: number | null;
  acceleration_px_s2: number | null;
  expansion_velocity_mm_s: number | null;
  expansion_velocity_sigma_mm_s: number | null;
  acceleration_mm_s2: number | null;
  centroid_displacement_mm: number | null;
  limb_radius_px: number | null;
  limb_radius_sigma_px: number | null;
  limb_center_x_px: number | null;
  limb_center_y_px: number | null;
  limb_coverage: number | null;
  limb_arc_deg: number | null;
  limb_rms_px: number | null;
  limb_fit_ok: boolean | null;
  limb_radius_mm: number | null;
  limb_radius_sigma_mm: number | null;
  warnings: string[];
  contour_px?: [number, number][] | null;
  [key: string]: unknown;
}

export interface VideoMetadata {
  filename: string;
  container: string;
  codec_fourcc: string;
  codec_name: string | null;
  width: number;
  height: number;
  nominal_fps: number;
  reported_frame_count: number;
  duration_s: number | null;
  file_size_bytes: number;
  kind: "video" | "image-sequence";
  frame_times_s?: number[] | null;
}

export interface AnalysisResult {
  schema: string;
  engine_version: string;
  experiment_id: string;
  video: VideoMetadata;
  timestamp_source: string;
  calibration: Calibration | null;
  config: AnalysisConfig;
  summary: AnalysisSummary;
  issues: ValidationIssue[];
  measurements: FlameMeasurement[];
}

export interface ProcessingJob {
  id: string;
  experiment_id: string;
  status: JobState;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: number;
  frames_processed: number;
  message: string;
  error: string | null;
  input_ref: string;
  config?: AnalysisConfig | null;
  calibration?: Calibration | null;
  summary?: AnalysisSummary | null;
  issues?: ValidationIssue[] | null;
  duration_s?: number | null;
  type?: string;
}

/** A live per-frame telemetry event from the WebSocket or polling endpoint. */
export interface FrameTelemetry {
  seq: number;
  frame_index: number;
  timestamp_s: number;
  status: FlameMeasurement["status"];
  fraction: number;
  frames_analyzed: number;
  elapsed_s: number;
  equivalent_radius_px: number | null;
  radius_mm: number | null;
  limb_fit_ok: boolean | null;
  limb_radius_px: number | null;
  limb_radius_mm: number | null;
  limb_center_px: [number, number] | null;
  centroid_px: [number, number] | null;
  confidence: number;
  circularity: number | null;
  contour_px: [number, number][] | null;
  warnings: string[];
}

export interface PredictionResult {
  quantity_class: "predicted";
  model_version: string;
  median_lifetime_s: number;
  interval: { level: number; lower_s: number; upper_s: number; includes_parameter_uncertainty: boolean; sigma_inflation_cross_validated: number };
  warnings: string[];
  population: string;
  limitations: string[];
  prediction_id?: string;
}

export interface PredictionRecord {
  id: string;
  created_at: string;
  experiment_id: string | null;
  model_version: string;
  inputs: Record<string, number>;
  result: PredictionResult;
  label: string;
}

export interface CoefficientRow { term: string; coef: number; se: number; time_ratio: number; time_ratio_ci95: [number, number]; p_value: number }

export interface CandidateMetrics {
  candidate: string;
  distribution: string;
  features: string[];
  n: number;
  n_events: number;
  n_groups: number;
  c_index: number;
  c_index_within_day: number;
  events_median_abs_log_error: number;
  events_median_abs_error_s: number;
  events_80pct_interval_coverage: number;
  censored_upper_bound_consistent: number | null;
  fold_failures: number;
}

export interface ModelMetadata {
  model_version: string;
  created_at: string;
  population: string;
  target: { name: string; definition: string; censoring: string };
  training_data: { file: string; sha256: string; n: number; n_events: number; test_days: string[]; source: string };
  distribution: "weibull" | "lognormal";
  l2: number;
  features: { name: string; description: string; unit: string }[];
  feature_ranges: Record<string, { min: number; max: number; observed_values: number[] | null }>;
  coefficient_table_standardized: CoefficientRow[];
  interval_inflation: { level: number; factor: number; coverage_before: number; coverage_after: number; n_events: number; method: string };
  limitations: string[];
  standardizer: { mean: number[]; std: number[] };
  coef: number[];
  log_sigma: number;
  converged: boolean;
  validation: { scheme: string; selected: CandidateMetrics; baseline_intercept_only: CandidateMetrics; baseline_note: string; candidates: CandidateMetrics[] };
}

export interface CvPredictions {
  metrics: { n_events: number; n_censored: number; r2_log: number | null; rmse_log: number; mae_s: number; median_abs_error_s: number; note: string };
  rows: { test_point: string; group: string; time_s: number; event: boolean; pred_q10_s: number; pred_median_s: number; pred_q90_s: number; [k: string]: unknown }[];
}

export interface DatasetMetadata {
  id: string;
  title: string;
  data_class: DataClass;
  rows: number;
  file_format: string;
  built_at: string | null;
  source_files: number;
  detection_config: Record<string, unknown> | null;
  provenance: { source: string; license: string; doi: string; build: string };
  quality_report: QualityReport | null;
  columns: string[];
}

export interface QualityReport {
  schema: string;
  test_points: number;
  outcomes: Record<string, number>;
  outcome_vs_nasa_stop_reason: Record<string, Record<string, number>>;
  flag_counts: Record<string, number>;
  experimental_table_corrections: { "Test Day": string; corrections: string }[];
  known_source_discrepancies: string[];
  caveats: string[];
}

export interface VariableStats {
  name: string;
  kind: "numeric" | "categorical";
  missing_fraction: number;
  unit: string | null;
  min?: number; max?: number; mean?: number; std?: number; median?: number; outliers_iqr?: number;
  histogram?: { counts: number[]; edges: number[] };
  top_values?: [string, number][];
}

export interface DatasetStats {
  rows: number;
  columns: number;
  duplicate_rows: number;
  duplicate_test_points: number | null;
  completeness: number;
  variables: VariableStats[];
  quality_report: QualityReport | null;
}

export type TestPointRow = Record<string, string | number | boolean | null>;

export interface Sample {
  id: string;
  title: string;
  data_class: DataClass;
  source: string;
  download_hint?: string;
  test_point?: string;
  conditions: Record<string, unknown>;
  calibration: Calibration;
  analysis_config: AnalysisConfig;
  available: boolean;
  generated?: boolean;
}

export type ReportBlock =
  | { type: "p"; text: string }
  | { type: "list"; items: string[] }
  | { type: "kv"; rows: [string, unknown][] }
  | { type: "table"; title?: string; columns: string[]; rows: unknown[][] }
  | { type: "figure"; id: string; title: string; x: string; y: string; series: { name: string; class: QuantityKind; points: [number, number][] }[] };

export interface ScientificReport {
  id: string;
  created_at: string;
  experiment_id: string | null;
  title: string;
  report_type: "experiment" | "comparison";
  status: "completed" | "failed";
  sections: string[];
  formats: ("pdf" | "json" | "csv")[];
  error: string | null;
  content?: { schema: string; title: string; generated_at: string; sections: { id: string; title: string; blocks: ReportBlock[] }[] };
}

export interface SystemStatus {
  api_version: string;
  engine_version: string;
  database: { ok: boolean; backend: string };
  experiments: { total: number; by_status: Record<string, number> };
  jobs: { by_status: Record<string, number>; active: number; workers: number };
  model: { loaded: boolean; version: string | null; error: string | null };
  datasets: { sflame_test_points: number | null };
  samples: { available: number; total: number };
  storage: { used_by_app_bytes: number; disk_free_bytes: number };
  runtime: { python: string; opencv: string; ffmpeg: boolean; platform: string };
  auth_required_for_writes: boolean;
  recovery_on_startup: { failed_interrupted: number; requeued: number };
  resources: {
    cpu_count: number | null;
    load_average: { "1m": number; "5m": number; "15m": number } | null;
    cpu_load_fraction_1m?: number;
    memory: { total_bytes: number; available_bytes: number; used_fraction: number } | null;
    process_max_rss_bytes: number;
    gpu: null;
    gpu_note: string;
  };
  processing: { completed_jobs_timed: number; average_duration_s: number | null; throughput_frames_per_s: number | null };
}

export interface ActivityEvent { time: string; kind: string; title: string; experiment_id?: string | null; job_id?: string; prediction_id?: string; report_id?: string }

export interface LogRecord { time: string; level: string; logger: string; message: string }

export interface WorkspaceSettings {
  workspace_name: string;
  units: "mm" | "px";
  date_format: "iso" | "local";
  default_analysis_config: AnalysisConfig;
  default_model: string;
  export_format: "csv" | "json";
}

export interface SettingsResponse {
  settings: WorkspaceSettings;
  server: { max_upload_mb: number; max_workers: number; rate_limit_per_minute: number; auth_required_for_writes: boolean; database_backend: string; telemetry_buffer: number };
}

export interface PreviewResponse { measurement: FlameMeasurement; mask_png_base64: string | null; overlay_jpeg_base64: string | null }
