// All backend access goes through this module; pages never build URLs or call axios directly.
import axios, { AxiosError } from "axios";
import type {
  ActivityEvent, AnalysisConfig, AnalysisResult, Calibration, CvPredictions, DatasetMetadata, DatasetStats, Experiment,
  ExperimentCreate, LogRecord, ModelMetadata, PredictionRecord, PredictionResult, PreviewResponse, ProcessingJob, Sample,
  ScientificReport, SettingsResponse, SystemStatus, TestPointRow, VideoMetadata, WorkspaceSettings,
} from "../types/api";

export const API_KEY_STORAGE = "fif.apiKey";

function storedKey(): string | null {
  try { return window.localStorage.getItem(API_KEY_STORAGE); } catch { return null; }
}

export const http = axios.create({ baseURL: "", timeout: 60_000 });
http.interceptors.request.use((cfg) => {
  const key = storedKey();
  if (key && cfg.method && cfg.method.toLowerCase() !== "get") cfg.headers.set("X-API-Key", key);
  return cfg;
});

/** A readable error message from the API's {"error": {"message"}} envelope or a network failure. */
export function errorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as { error?: { message?: string }; detail?: unknown } | undefined;
    if (data?.error?.message) return data.error.message;
    if (Array.isArray(data?.detail)) return (data!.detail as { msg: string; loc: string[] }[]).map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
    if (!err.response) return "The analysis server is not reachable. Start it with `uvicorn backend.app:app` and retry.";
    return `Request failed (${err.response.status}).`;
  }
  return err instanceof Error ? err.message : String(err);
}

const get = async <T>(url: string, params?: Record<string, unknown>) => (await http.get<T>(url, { params })).data;
const post = async <T>(url: string, body?: unknown) => (await http.post<T>(url, body)).data;

export const api = {
  health: () => get<{ status: string; api_version: string }>("/api/health"),
  systemStatus: () => get<SystemStatus>("/api/system/status"),
  activity: (limit = 30) => get<ActivityEvent[]>("/api/activity", { limit }),
  logs: (q?: string) => get<LogRecord[]>("/api/logs", { q: q || undefined }),
  jobs: (status?: string, limit = 100) => get<ProcessingJob[]>("/api/jobs", { status, limit }),
  job: (id: string) => get<ProcessingJob>(`/api/jobs/${id}`),
  cancelJob: (id: string) => post<{ status: string }>(`/api/jobs/${id}/cancel`),
  jobResult: (id: string, contours = false) => get<AnalysisResult>(`/api/jobs/${id}/result`, { contours }),
  jobResultCsvUrl: (id: string) => `/api/jobs/${id}/result?format=csv`,

  experiments: (opts: { includeArchived?: boolean; status?: string; limit?: number } = {}) =>
    get<Experiment[]>("/api/experiments", { include_archived: opts.includeArchived, status: opts.status, limit: opts.limit ?? 500 }),
  experiment: (id: string) => get<Experiment>(`/api/experiments/${id}`),
  createExperiment: (body: ExperimentCreate) => post<Experiment>("/api/experiments", body),
  updateExperiment: async (id: string, body: Partial<ExperimentCreate> & { archived?: boolean; calibration?: Calibration | null }) =>
    (await http.patch<Experiment>(`/api/experiments/${id}`, body)).data,
  deleteExperiment: async (id: string) => { await http.delete(`/api/experiments/${id}`); },
  duplicateExperiment: (id: string) => post<Experiment>(`/api/experiments/${id}/duplicate`),
  experimentJobs: (id: string) => get<ProcessingJob[]>(`/api/experiments/${id}/jobs`),
  reanalyze: (id: string, analysis_config?: AnalysisConfig) => post<ProcessingJob>(`/api/experiments/${id}/reanalyze`, analysis_config ? { analysis_config } : {}),
  media: (id: string) => get<VideoMetadata>(`/api/experiments/${id}/media`),
  frameUrl: (id: string, index: number, maxWidth = 1400) => `/api/experiments/${id}/frames/${index}.jpg?max_width=${maxWidth}`,
  preview: (id: string, frame_index: number, analysis_config?: AnalysisConfig, calibration?: Calibration | null) =>
    post<PreviewResponse>(`/api/experiments/${id}/preview`, { frame_index, analysis_config, calibration: calibration ?? undefined }),

  analyzeVideo: async (file: File, opts: { experimentId?: string; name?: string; analysisConfig?: AnalysisConfig; calibration?: Calibration | null },
    onUpload?: (fraction: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    if (opts.experimentId) form.append("experiment_id", opts.experimentId);
    if (opts.name) form.append("name", opts.name);
    if (opts.analysisConfig) form.append("analysis_config", JSON.stringify(opts.analysisConfig));
    if (opts.calibration) form.append("calibration", JSON.stringify(opts.calibration));
    return (await http.post<ProcessingJob>("/api/analyze-video", form, {
      timeout: 0, onUploadProgress: (e) => onUpload && e.total && onUpload(e.loaded / e.total),
    })).data;
  },
  samples: () => get<Sample[]>("/api/samples"),
  analyzeSample: (sample_id: string, experiment_id?: string, analysis_config?: AnalysisConfig) =>
    post<ProcessingJob>("/api/analyze-sample", { sample_id, experiment_id, analysis_config }),

  predict: (inputs: Record<string, number>, experiment_id?: string, interval = 0.8) =>
    post<PredictionResult>("/api/predict", { inputs, experiment_id, interval }),
  predictions: (experiment_id?: string) => get<PredictionRecord[]>("/api/predictions", { experiment_id }),
  models: () => get<{ models: ModelMetadata[]; error?: string }>("/api/models"),
  cvPredictions: () => get<CvPredictions>("/api/models/cv-predictions"),

  datasets: () => get<{ datasets: DatasetMetadata[] }>("/api/datasets"),
  datasetStats: () => get<DatasetStats>("/api/datasets/sflame/stats"),
  testPoints: (filters: { outcome?: string; flow_programme?: string; test_day?: string; limit?: number } = {}) =>
    get<{ total: number; rows: TestPointRow[] }>("/api/datasets/sflame/test-points", { ...filters, limit: filters.limit ?? 1000 }),

  reports: (experiment_id?: string) => get<ScientificReport[]>("/api/reports", { experiment_id }),
  report: (id: string) => get<ScientificReport>(`/api/reports/${id}`),
  createReport: (body: { experiment_id?: string; comparison_ids?: string[]; sections?: string[]; title?: string }) =>
    post<ScientificReport>("/api/reports", body),
  reportDownloadUrl: (id: string, format: "pdf" | "json" | "csv") => `/api/reports/${id}/download?format=${format}`,
  exportExperiment: async (experiment_id: string, format: "json" | "csv") =>
    (await http.post<Blob>("/api/export", { experiment_id, format }, { responseType: "blob" })).data,

  settings: () => get<SettingsResponse>("/api/settings"),
  saveSettings: async (body: Partial<WorkspaceSettings>) => (await http.put<SettingsResponse>("/api/settings", body)).data,
  docs: () => get<{ id: string; file: string }[]>("/api/docs"),
  doc: (id: string) => get<string>(`/api/docs/${id}`),
};

/** Fetch a URL (respecting the API key) and save it with a file name; real file download, not a fake link. */
export async function downloadUrl(url: string, filename: string): Promise<void> {
  const res = await http.get<Blob>(url, { responseType: "blob" });
  saveBlob(res.data, filename);
}

export function saveBlob(data: Blob, filename: string): void {
  const href = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 2000);
}

export function saveText(text: string, filename: string, type = "text/plain"): void {
  saveBlob(new Blob([text], { type }), filename);
}

/** WebSocket URL for live job telemetry (same origin; Vite proxies it in development). */
export function jobSocketUrl(jobId: string, after = -1): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const key = storedKey();
  return `${proto}//${window.location.host}/api/jobs/${jobId}/ws?after=${after}${key ? `&api_key=${encodeURIComponent(key)}` : ""}`;
}
