import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DataTable, MetricCard, StatusPill, IntervalBar } from "../design-system";
import { fmt, fmtSigma, pct } from "../lib/format";
import { effectiveUnits, measurementsCsv, quantity, series } from "../lib/analysis";
import Markdown from "../components/Markdown";
import type { AnalysisResult, FlameMeasurement } from "../types/api";

const m = (i: number, extra: Partial<FlameMeasurement> = {}): FlameMeasurement => ({
  experiment_id: "E", frame_index: i, timestamp_s: i / 10, status: "detected", confidence: 0.9, segmentation_quality: 1, contrast: 0.5, n_candidates: 1,
  centroid_x_px: 10, centroid_y_px: 10, enclosing_center_x_px: null, enclosing_center_y_px: null, enclosing_radius_px: null, equivalent_radius_px: 5 + i,
  equivalent_radius_sigma_px: 0.2, equivalent_diameter_px: null, area_px2: null, perimeter_px: null, circularity: 0.9, eccentricity: 0.1, boundary_roughness: 0.01,
  touches_border: false, radius_mm: (5 + i) / 10, radius_sigma_mm: 0.03, diameter_mm: null, area_mm2: null, perimeter_mm: null, equivalent_volume_mm3: null,
  equivalent_volume_sigma_mm3: null, radius_smoothed_px: null, expansion_velocity_px_s: null, expansion_velocity_sigma_px_s: null, acceleration_px_s2: null,
  expansion_velocity_mm_s: null, expansion_velocity_sigma_mm_s: null, acceleration_mm_s2: null, centroid_displacement_mm: null, limb_radius_px: null,
  limb_radius_sigma_px: null, limb_center_x_px: null, limb_center_y_px: null, limb_coverage: null, limb_arc_deg: null, limb_rms_px: null, limb_fit_ok: null,
  limb_radius_mm: null, limb_radius_sigma_mm: null, warnings: [], ...extra,
});
const result = (calibrated: boolean, ms: FlameMeasurement[]) => ({ experiment_id: "E", summary: { calibrated }, measurements: ms }) as unknown as AnalysisResult;

describe("formatting", () => {
  it("renders missing values as a dash and rounds sigma to two significant figures", () => {
    expect(fmt(null)).toBe("—");
    expect(fmt(-1.234, 1)).toBe("−1.2");
    expect(fmtSigma(12.3456, 0.0234)).toEqual(["12.346", "0.023"]);
    expect(fmtSigma(5, null)).toEqual(["5.00", null]);
    expect(pct(0.413)).toBe("41 %");
  });
});

describe("analysis helpers", () => {
  it("keeps frames without a value as gaps instead of interpolating", () => {
    const r = result(true, [m(0), m(1, { radius_mm: null, status: "not_detected" }), m(2)]);
    const s = series(r, quantity("eq_radius"), "mm");
    expect(s.points.map((p) => p.y)).toEqual([0.5, null, 0.7]);
    expect(s.points[0].lo).toBeCloseTo(0.47);
  });
  it("only offers millimetres for calibrated analyses", () => {
    expect(effectiveUnits(result(false, []), "mm")).toBe("px");
    expect(effectiveUnits(result(true, []), "mm")).toBe("mm");
  });
  it("hides limb radii whose fit was rejected", () => {
    const r = result(true, [m(0, { limb_radius_mm: 3, limb_fit_ok: false }), m(1, { limb_radius_mm: 4, limb_fit_ok: true })]);
    expect(series(r, quantity("limb_radius"), "mm").points.map((p) => p.y)).toEqual([null, 4]);
  });
  it("exports CSV with quoting and empty cells for missing values", () => {
    const csv = measurementsCsv(result(true, [m(0, { warnings: ["a", "b"] })]), ["frame_index", "limb_radius_mm", "warnings"]);
    expect(csv.split("\n")[1]).toBe('0,,"a; b"');
  });
});

describe("design system", () => {
  it("shows a dash for a metric without a value and labels the quantity class", () => {
    render(<MetricCard label="Peak radius" quantity="predicted" />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByTitle("Predicted quantity")).toBeInTheDocument();
  });
  it("maps job states to readable pills", () => {
    render(<StatusPill state="processing" />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });
  it("describes an interval for screen readers, including the observed value", () => {
    render(<IntervalBar median={10} lower={5} upper={20} observed={12} unit="s" label="Lifetime" />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Lifetime: 10 s, interval 5 to 20 s, observed 12 s");
  });
  it("sorts table rows and shows the empty text", () => {
    const { rerender } = render(<DataTable columns={[{ key: "a", label: "A", numeric: true }]} rows={[{ a: 2 }, { a: 1 }]} rowKey={(r) => String(r.a)} initialSort={{ key: "a", dir: "asc" }} />);
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("1");
    rerender(<DataTable columns={[{ key: "a", label: "A" }]} rows={[]} rowKey={() => ""} emptyText="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("markdown", () => {
  it("renders headings, lists and code without injecting HTML", () => {
    const { container } = render(<Markdown source={"# Title\n\n- one `x`\n- two\n\n<script>alert(1)</script>\n\n```\ncode\n```"} />);
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  });
});

describe("app shell", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  it("renders the seven navigation categories and reports an unreachable API honestly", async () => {
    const { http } = await import("../services/api");
    vi.spyOn(http, "get").mockRejectedValue(Object.assign(new (await import("axios")).AxiosError("Network Error"), { response: undefined }));
    const { default: App } = await import("../App");
    render(<MemoryRouter initialEntries={["/system"]}><App /></MemoryRouter>);
    for (const label of ["Mission Control", "Experiments", "Video Intelligence", "Analytics", "Prediction", "Data & Reports", "System"])
      expect(screen.getAllByRole("link", { name: label }).length).toBeGreaterThan(0);
    expect(await screen.findByText("The analysis server is not reachable.", {}, { timeout: 3000 })).toBeInTheDocument();
  });
});
