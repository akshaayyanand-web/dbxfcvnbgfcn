// Turn an AnalysisResult into chart series and viewer overlays. Nothing is interpolated or invented: frames
// without a value are gaps, and quantity classes follow FIELD_DEFINITIONS in backend/vision/cv_engine.py.
import type { AnalysisResult, FlameMeasurement, FrameTelemetry, QuantityKind } from "../types/api";
import type { Series } from "../charts";
import type { FrameOverlay } from "../components/VideoViewer";
import { fmt } from "./format";

export type Units = "mm" | "px";

export interface Quantity {
  id: string; label: string; unit: (u: Units) => string; kind: QuantityKind;
  value: (m: FlameMeasurement, u: Units) => number | null; sigma?: (m: FlameMeasurement, u: Units) => number | null;
  needsCalibration?: boolean;
}

const v = (x: unknown) => (typeof x === "number" && Number.isFinite(x) ? x : null);

export const QUANTITIES: Quantity[] = [
  { id: "eq_radius", label: "Equivalent radius", kind: "image_derived", unit: (u) => u, value: (m, u) => v(u === "mm" ? m.radius_mm : m.equivalent_radius_px),
    sigma: (m, u) => v(u === "mm" ? m.radius_sigma_mm : m.equivalent_radius_sigma_px) },
  { id: "limb_radius", label: "Shell-limb radius", kind: "image_derived", unit: (u) => u, value: (m, u) => (m.limb_fit_ok ? v(u === "mm" ? m.limb_radius_mm : m.limb_radius_px) : null),
    sigma: (m, u) => v(u === "mm" ? m.limb_radius_sigma_mm : m.limb_radius_sigma_px) },
  { id: "velocity", label: "Expansion velocity dr/dt", kind: "calculated", unit: (u) => `${u}/s`, value: (m, u) => v(u === "mm" ? m.expansion_velocity_mm_s : m.expansion_velocity_px_s),
    sigma: (m, u) => v(u === "mm" ? m.expansion_velocity_sigma_mm_s : m.expansion_velocity_sigma_px_s) },
  { id: "acceleration", label: "Acceleration d²r/dt²", kind: "calculated", unit: (u) => `${u}/s²`, value: (m, u) => v(u === "mm" ? m.acceleration_mm_s2 : m.acceleration_px_s2) },
  { id: "area", label: "Projected area", kind: "image_derived", unit: (u) => (u === "mm" ? "mm²" : "px²"), value: (m, u) => v(u === "mm" ? m.area_mm2 : m.area_px2) },
  { id: "volume", label: "Equivalent spherical volume", kind: "calculated", unit: () => "mm³", value: (m) => v(m.equivalent_volume_mm3), sigma: (m) => v(m.equivalent_volume_sigma_mm3), needsCalibration: true },
  { id: "circularity", label: "Circularity", kind: "image_derived", unit: () => "", value: (m) => v(m.circularity) },
  { id: "eccentricity", label: "Eccentricity", kind: "image_derived", unit: () => "", value: (m) => v(m.eccentricity) },
  { id: "roughness", label: "Boundary roughness", kind: "image_derived", unit: () => "", value: (m) => v(m.boundary_roughness) },
  { id: "drift", label: "Centroid displacement", kind: "calculated", unit: () => "mm", value: (m) => v(m.centroid_displacement_mm), needsCalibration: true },
  { id: "confidence", label: "Detection confidence", kind: "calculated", unit: () => "", value: (m) => v(m.confidence) },
  { id: "contrast", label: "Flame / background contrast", kind: "image_derived", unit: () => "", value: (m) => v(m.contrast) },
];

export const quantity = (id: string) => QUANTITIES.find((q) => q.id === id)!;

/** Units actually available: mm only when the analysis was calibrated. */
export const effectiveUnits = (r: AnalysisResult | undefined, pref: Units): Units => (r?.summary.calibrated ? pref : "px");

export function series(r: AnalysisResult, q: Quantity, u: Units, opts: { name?: string; color?: number; band?: boolean } = {}): Series {
  return {
    id: `${r.experiment_id}-${q.id}`, name: opts.name ?? q.label, kind: q.kind, color: opts.color, band: opts.band ?? !!q.sigma,
    points: r.measurements.map((m) => {
      const y = q.value(m, u), s = q.sigma?.(m, u) ?? null;
      return { x: m.timestamp_s, y, lo: y != null && s != null ? y - s : null, hi: y != null && s != null ? y + s : null };
    }),
  };
}

export function hasValues(r: AnalysisResult, q: Quantity, u: Units): boolean {
  return r.measurements.some((m) => q.value(m, u) != null);
}

/** Primary radius according to the configured method (limb or equivalent). */
export function primaryRadius(r: AnalysisResult): Quantity {
  return r.summary.radius_method === "limb" ? quantity("limb_radius") : quantity("eq_radius");
}

export function nearestMeasurement(r: AnalysisResult | undefined, frame: number): FlameMeasurement | undefined {
  if (!r?.measurements.length) return undefined;
  let best = r.measurements[0];
  for (const m of r.measurements) if (Math.abs(m.frame_index - frame) < Math.abs(best.frame_index - frame)) best = m;
  return best;
}

export function overlayFromMeasurement(m: FlameMeasurement | undefined, units: Units): FrameOverlay | null {
  if (!m) return null;
  const centroid = m.centroid_x_px != null && m.centroid_y_px != null ? [m.centroid_x_px, m.centroid_y_px] as [number, number] : null;
  const limb = m.limb_radius_px != null && m.limb_center_x_px != null && m.limb_center_y_px != null
    ? { cx: m.limb_center_x_px, cy: m.limb_center_y_px, r: m.limb_radius_px, ok: !!m.limb_fit_ok } : null;
  const rText = m.limb_fit_ok && m.limb_radius_mm != null && units === "mm" ? `R limb ${fmt(m.limb_radius_mm, 2)} mm`
    : m.radius_mm != null && units === "mm" ? `R eq ${fmt(m.radius_mm, 2)} mm` : m.equivalent_radius_px != null ? `R eq ${fmt(m.equivalent_radius_px, 1)} px` : null;
  return { status: m.status, confidence: m.confidence, timestamp_s: m.timestamp_s, contour: m.contour_px ?? null, centroid,
    equivalentRadius: m.equivalent_radius_px, limb, radiusText: rText };
}

export function overlayFromTelemetry(t: FrameTelemetry | undefined): FrameOverlay | null {
  if (!t) return null;
  const limb = t.limb_center_px && t.limb_radius_px != null ? { cx: t.limb_center_px[0], cy: t.limb_center_px[1], r: t.limb_radius_px, ok: !!t.limb_fit_ok } : null;
  return { status: t.status, confidence: t.confidence, timestamp_s: t.timestamp_s, contour: t.contour_px, centroid: t.centroid_px,
    equivalentRadius: t.equivalent_radius_px, limb, radiusText: t.radius_mm != null ? `R ${fmt(t.radius_mm, 2)} mm` : t.equivalent_radius_px != null ? `R ${fmt(t.equivalent_radius_px, 1)} px` : null };
}

/** Measurements to CSV text (client-side export of what is on screen). */
export function measurementsCsv(r: AnalysisResult, cols: string[]): string {
  const esc = (x: unknown) => (x == null ? "" : Array.isArray(x) ? `"${x.join("; ")}"` : typeof x === "string" && /[",\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : String(x));
  return [cols.join(","), ...r.measurements.map((m) => cols.map((c) => esc(m[c])).join(","))].join("\n");
}
