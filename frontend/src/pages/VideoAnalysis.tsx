// Video Intelligence: input, calibration and segmentation on the left, the frame viewer with overlays and synced
// charts in the centre, live telemetry and the current frame's measurement on the right.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Upload } from "lucide-react";
import { Alert, Button, EmptyState, Field, Kv, LoadingBlock, Panel, Progress, Segmented, SelectField, StatusPill } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync, useJobTelemetry } from "../hooks";
import { useApp } from "../store/app";
import VideoViewer, { LAYERS, type Layer } from "../components/VideoViewer";
import { TimeSeriesChart } from "../charts";
import { DataClassPill, ErrorState, IssueList, PageHead, useExperimentBundle } from "../components/common";
import { effectiveUnits, nearestMeasurement, overlayFromMeasurement, overlayFromTelemetry, primaryRadius, quantity, series } from "../lib/analysis";
import { duration, fmt, fmtSigma } from "../lib/format";
import type { AnalysisConfig, FrameTelemetry, PreviewResponse, ProcessingJob, SegmentationConfig } from "../types/api";

const jobSeconds = (j: ProcessingJob) => j.duration_s ?? (j.started_at && j.finished_at ? (Date.parse(`${j.finished_at}Z`) - Date.parse(`${j.started_at}Z`)) / 1000 : null);

const METHODS: { value: NonNullable<SegmentationConfig["method"]>; label: string }[] = [
  { value: "otsu", label: "Otsu (automatic)" }, { value: "fixed", label: "Fixed threshold" }, { value: "adaptive", label: "Adaptive" },
  { value: "hsv", label: "HSV colour" }, { value: "background_subtraction", label: "Background subtraction" },
];

function InputPanel({ experimentId, hasInput, onStarted }: { experimentId: string | null; hasInput: boolean; onStarted: (expId: string) => void }) {
  const { notify, setExperiment } = useApp();
  const samples = useAsync(() => api.samples(), []);
  const [file, setFile] = useState<File | null>(null);
  const [sample, setSample] = useState("");
  const [up, setUp] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const start = async (kind: "file" | "sample") => {
    setBusy(true);
    try {
      const job = kind === "file" && file
        ? (setUp(0), await api.analyzeVideo(file, { experimentId: experimentId ?? undefined, name: experimentId ? undefined : file.name.replace(/\.[^.]+$/, "") }, setUp))
        : await api.analyzeSample(sample, experimentId && !hasInput ? experimentId : undefined);
      setExperiment(job.experiment_id); onStarted(job.experiment_id);
      notify("info", "Analysis queued", kind === "file" ? file?.name : sample);
      setFile(null);
    } catch (e) { notify("bad", "Could not start the analysis", errorMessage(e)); } finally { setBusy(false); setUp(null); }
  };
  return (
    <Panel title="Input" eyebrow="Step 1">
      <div className="dropzone" role="button" tabIndex={0} onClick={() => ref.current?.click()} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") ref.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("is-over"); }} onDragLeave={(e) => e.currentTarget.classList.remove("is-over")}
        onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("is-over"); setFile(e.dataTransfer.files[0] ?? null); }} style={{ padding: 20 }}>
        <Upload size={20} aria-hidden />
        <span className="body-s">{file ? file.name : "Drop an MP4, MOV or AVI"}</span>
        <input ref={ref} type="file" hidden accept=".mp4,.mov,.avi" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      {file && <Button variant="ink" busy={busy} onClick={() => start("file")}>{experimentId ? "Upload to this experiment" : "Upload as new experiment"}</Button>}
      {up != null && <Progress value={up} label="Uploading" />}
      <hr className="divider" />
      <SelectField label="Or a bundled sample" value={sample} onChange={(e) => setSample(e.target.value)}>
        <option value="">Choose…</option>
        {samples.data?.map((s) => <option key={s.id} value={s.id} disabled={!s.available}>{s.title}{s.available ? "" : " (not downloaded)"}</option>)}
      </SelectField>
      {sample && <span className="body-s subtle">{samples.data?.find((s) => s.id === sample)?.source}</span>}
      <Button busy={busy} disabled={!sample} onClick={() => start("sample")}>Analyse sample</Button>
    </Panel>
  );
}

export default function VideoAnalysis() {
  const { experimentId, units, notify } = useApp();
  const b = useExperimentBundle(experimentId, true);
  const exp = b.exp.data;
  const hasInput = !!exp?.video_ref;
  const media = useAsync(() => api.media(experimentId!), [experimentId, exp?.video_ref], !!experimentId && hasInput);
  const [jobId, setJobId] = useState<string | null>(null);
  const live = useJobTelemetry(jobId);
  const [frame, setFrame] = useState(0);
  const [follow, setFollow] = useState(true);
  const [layers, setLayers] = useState<Set<Layer>>(new Set(["contour", "limb", "centroid", "hud"]));
  const [cfg, setCfg] = useState<AnalysisConfig>({});
  const [calibrating, setCalibrating] = useState(false);
  const [calPts, setCalPts] = useState<[number, number][]>([]);
  const [knownMm, setKnownMm] = useState("6.35");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [chartQ, setChartQ] = useState("radius");

  // Track the running job for this experiment (also one started elsewhere).
  useEffect(() => { setJobId(b.running?.id ?? null); }, [b.running?.id]);
  useEffect(() => { if (live.job && ["completed", "failed", "cancelled"].includes(live.job.status)) { b.reload(); } }, [live.job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setCfg({ ...(exp?.analysis_config ?? {}) }); setFrame(0); setPreview(null); setCalPts([]); setCalibrating(false); }, [exp?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const liveByFrame = useMemo(() => new Map<number, FrameTelemetry>(live.events.map((e) => [e.frame_index, e])), [live.events]);
  const isLive = !!live.job && (live.job.status === "processing" || live.job.status === "queued");
  useEffect(() => { if (isLive && follow && live.latest) setFrame(live.latest.frame_index); }, [isLive, follow, live.latest]);

  const r = b.result.data;
  const u = effectiveUnits(r, units);
  // Open a finished analysis on its largest-flame frame rather than on (usually dark) frame 0.
  useEffect(() => {
    if (!r || isLive) return;
    const first = r.summary.peak_radius?.frame_index ?? r.measurements.find((x) => x.status === "detected")?.frame_index;
    if (first != null) setFrame(first);
  }, [r?.experiment_id, b.completed?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const m = isLive ? undefined : nearestMeasurement(r, frame);
  const overlay = isLive ? overlayFromTelemetry(liveByFrame.get(frame)) : m && m.frame_index === frame ? overlayFromMeasurement(m, u) : null;
  const step = Math.max(1, Number(cfg.frame_step ?? r?.config.frame_step ?? 1));
  const seg = cfg.segmentation ?? {};
  const setSeg = (patch: Partial<SegmentationConfig>) => setCfg({ ...cfg, segmentation: { ...seg, ...patch } });
  const toggle = (l: Layer) => setLayers((s) => { const n = new Set(s); if (n.has(l)) n.delete(l); else n.add(l); return n; });
  const onIndex = useCallback((i: number) => { setFrame(i); setFollow(false); }, []);
  const seekTime = (t: number) => {
    const target = r?.measurements.reduce((best, x) => (Math.abs(x.timestamp_s - t) < Math.abs(best.timestamp_s - t) ? x : best));
    if (target) onIndex(target.frame_index);
  };

  const pxDist = calPts.length === 2 ? Math.hypot(calPts[1][0] - calPts[0][0], calPts[1][1] - calPts[0][1]) : null;
  const saveCalibration = async () => {
    if (!exp || !pxDist) return;
    setBusy("cal");
    try {
      await api.updateExperiment(exp.id, { calibration: { known_length_mm: Number(knownMm), measured_length_px: pxDist, measured_length_sigma_px: 1, method: "two-point click on frame", image_width: media.data?.width, image_height: media.data?.height } });
      notify("ok", "Calibration saved", `${fmt(Number(knownMm) / pxDist, 5)} mm/px. Re-run the analysis to apply it.`);
      setCalibrating(false); setCalPts([]); b.reload();
    } catch (e) { notify("bad", "Calibration not saved", errorMessage(e)); } finally { setBusy(null); }
  };
  const runPreview = async () => {
    if (!exp) return;
    setBusy("preview");
    try { setPreview(await api.preview(exp.id, frame, cfg)); } catch (e) { notify("bad", "Preview failed", errorMessage(e)); } finally { setBusy(null); }
  };
  const runAnalysis = async () => {
    if (!exp) return;
    setBusy("run");
    try { const j = await api.reanalyze(exp.id, cfg); setJobId(j.id); setFollow(true); notify("info", "Analysis queued", exp.name); b.reload(); }
    catch (e) { notify("bad", "Could not start the analysis", errorMessage(e)); } finally { setBusy(null); }
  };

  const chartSeries = r ? (chartQ === "radius" ? [series(r, primaryRadius(r), u)] : chartQ === "velocity" ? [series(r, quantity("velocity"), u, { color: 1 })] : [series(r, quantity("confidence"), u, { color: 2, band: false })]) : [];
  const liveSeries = isLive ? [{ id: "live", name: "Radius (live, unsmoothed)", kind: "image_derived" as const, points: live.events.map((e) => ({ x: e.timestamp_s, y: u === "mm" && e.radius_mm != null ? (e.limb_fit_ok && e.limb_radius_mm != null ? e.limb_radius_mm : e.radius_mm) : (e.limb_fit_ok && e.limb_radius_px != null ? e.limb_radius_px : e.equivalent_radius_px) })) }] : [];

  return (
    <div className="page">
      <PageHead eyebrow="Video Intelligence" title={exp ? exp.name : "Analyse a flame video"}
        lede={exp ? <span className="row"><DataClassPill exp={exp} /><StatusPill state={exp.status} />{media.data && <span className="body-s subtle">{media.data.width}×{media.data.height} · {fmt(media.data.nominal_fps, 2)} fps · {media.data.reported_frame_count} frames</span>}</span>
          : "Upload a video or choose a sample. Frames are decoded on the server with the same decoder the analysis uses, so what you see is what is measured."}
        actions={exp && <Link to={`/experiments/${exp.id}`}><Button>Experiment details</Button></Link>} />

      <div className="vw">
        <div className="vw-col vw-left">
          <InputPanel experimentId={experimentId} hasInput={hasInput} onStarted={() => b.reload()} />
          {exp && hasInput && (<>
            <Panel title="Calibration" eyebrow="Step 2">
              {exp.calibration ? <Alert tone="ok" title={`${fmt(exp.calibration.mm_per_px ?? null, 5)} mm/px`}>{exp.calibration.method ?? "calibrated"} · ± {fmt(exp.calibration.mm_per_px_sigma ?? null, 5)}</Alert>
                : <Alert tone="warn" title="Not calibrated">Sizes will be in pixels only.</Alert>}
              <Button size="sm" variant={calibrating ? "ink" : "outline"} onClick={() => { setCalibrating(!calibrating); setCalPts([]); }}>{calibrating ? "Cancel calibration" : "Calibrate on frame"}</Button>
              {calibrating && (<>
                <span className="body-s muted">Click both ends of a feature of known size on the frame (e.g. the 6.35 mm burner sphere). Points: {calPts.length}/2.</span>
                <Field label="Known length" unit="mm" value={knownMm} onChange={(e) => setKnownMm(e.target.value)} inputMode="decimal" />
                {pxDist != null && <span className="data-s">{fmt(pxDist, 1)} px → {fmt(Number(knownMm) / pxDist, 5)} mm/px</span>}
                <Button size="sm" variant="ink" busy={busy === "cal"} disabled={!pxDist || !(Number(knownMm) > 0)} onClick={saveCalibration}>Save calibration</Button>
              </>)}
            </Panel>
            <Panel title="Segmentation" eyebrow="Step 3">
              <SelectField label="Method" value={seg.method ?? "otsu"} onChange={(e) => setSeg({ method: e.target.value as SegmentationConfig["method"] })}>
                {METHODS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </SelectField>
              <SelectField label="Channel" value={seg.channel ?? "max"} onChange={(e) => setSeg({ channel: e.target.value as SegmentationConfig["channel"] })}>
                {["max", "gray", "blue", "green", "red"].map((c) => <option key={c}>{c}</option>)}
              </SelectField>
              {(seg.method ?? "otsu") === "fixed" && <Field label="Fixed threshold" value={String(seg.fixed_threshold ?? 40)} onChange={(e) => setSeg({ fixed_threshold: Number(e.target.value) })} inputMode="numeric" />}
              <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <Field label="Blur kernel" value={String(seg.blur_kernel ?? 5)} onChange={(e) => setSeg({ blur_kernel: Number(e.target.value) })} inputMode="numeric" hint="odd" />
                <Field label="Min area" unit="px" value={String(seg.min_contour_area_px ?? 30)} onChange={(e) => setSeg({ min_contour_area_px: Number(e.target.value) })} inputMode="numeric" />
              </div>
              <SelectField label="Radius method" value={cfg.radius_method ?? "equivalent"} onChange={(e) => setCfg({ ...cfg, radius_method: e.target.value as AnalysisConfig["radius_method"] })}
                hint="Limb: circle fit to the shell edge, for hollow-shell flames. Equivalent: √(area/π).">
                <option value="equivalent">Equivalent (area)</option><option value="limb">Shell limb fit</option>
              </SelectField>
              <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <Field label="Frame step" value={String(cfg.frame_step ?? 1)} onChange={(e) => setCfg({ ...cfg, frame_step: Math.max(1, Number(e.target.value) || 1) })} inputMode="numeric" />
                <Field label="Scale" value={String(cfg.processing_scale ?? 1)} onChange={(e) => setCfg({ ...cfg, processing_scale: Number(e.target.value) })} inputMode="decimal" hint="0–1" />
              </div>
              <div className="row">
                <Button size="sm" busy={busy === "preview"} onClick={runPreview} disabled={!media.data}>Preview frame {frame}</Button>
                <Button size="sm" variant="lime" busy={busy === "run"} onClick={runAnalysis} disabled={isLive}>Run analysis</Button>
              </div>
            </Panel>
          </>)}
        </div>

        <div className="vw-col">
          {!experimentId ? <EmptyState eyebrow="No video" title="Choose an input to begin." body="Upload a video, pick a sample, or select an existing experiment in the bar above." />
            : b.exp.error ? <ErrorState error={b.exp.error} onRetry={b.reload} />
              : !exp ? <LoadingBlock rows={6} />
                : !hasInput ? <EmptyState title="This experiment has no video yet." body="Upload one with the Input panel; it will be attached to this experiment." />
                  : media.error ? <ErrorState error={media.error} onRetry={media.reload} title="The video could not be opened" />
                    : !media.data ? <div className="viewer"><div className="viewer-msg">Opening video…</div></div>
                      : <VideoViewer experimentId={exp.id} media={media.data} index={frame} onIndex={onIndex} overlay={overlay} layers={layers} step={step}
                        calibrating={calibrating} calPoints={calPts} onCalClick={(p) => setCalPts((pts) => (pts.length >= 2 ? [p] : [...pts, p]))} />}
          {media.data && (
            <div className="layer-toggles" role="group" aria-label="Overlay layers">
              {LAYERS.map((l) => <label key={l.id} className="fif-check"><input type="checkbox" checked={layers.has(l.id)} onChange={() => toggle(l.id)} /><span className="swatch" style={{ background: l.color }} />{l.label}</label>)}
              {isLive && <label className="fif-check"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />Follow live frame</label>}
            </div>
          )}
          {preview && (
            <Panel title={`Segmentation preview · frame ${preview.measurement.frame_index}`} eyebrow="Not saved; run the analysis to apply" actions={<Button size="sm" variant="ghost" onClick={() => setPreview(null)}>Close</Button>}>
              <div className="grid g-2">
                {preview.overlay_jpeg_base64 && <figure style={{ margin: 0 }}><img src={`data:image/jpeg;base64,${preview.overlay_jpeg_base64}`} alt="Segmentation overlay" style={{ borderRadius: 12, width: "100%" }} /><figcaption className="data-s subtle">Overlay</figcaption></figure>}
                {preview.mask_png_base64 && <figure style={{ margin: 0 }}><img src={`data:image/png;base64,${preview.mask_png_base64}`} alt="Binary mask" style={{ borderRadius: 12, width: "100%", background: "#000" }} /><figcaption className="data-s subtle">Mask (processing resolution)</figcaption></figure>}
              </div>
              <Kv rows={[["Status", <StatusPill key="s" state={preview.measurement.status} />], ["Confidence", fmt(preview.measurement.confidence, 2)], ["Equivalent radius", `${fmt(preview.measurement.equivalent_radius_px, 1)} px`], ["Limb radius", preview.measurement.limb_fit_ok ? `${fmt(preview.measurement.limb_radius_px, 1)} px` : "no accepted fit"], ["Warnings", preview.measurement.warnings.join("; ") || "none"]]} />
            </Panel>
          )}
          {(r || isLive) && (
            <Panel title={isLive ? "Live radius" : "Synced measurements"} eyebrow={isLive ? `streaming via ${live.transport}` : "Click the chart to jump to a frame"}>
              {isLive ? <TimeSeriesChart series={liveSeries} xLabel="time (s)" yLabel={`radius (${u})`} height={220} cursorX={liveByFrame.get(frame)?.timestamp_s} />
                : <TimeSeriesChart series={chartSeries} xLabel="time (s)" yLabel={chartQ === "radius" ? `radius (${u})` : chartQ === "velocity" ? `dr/dt (${u}/s)` : "confidence"} height={240}
                  cursorX={m?.timestamp_s} onPick={seekTime}
                  actions={<Segmented label="Quantity" value={chartQ} onChange={setChartQ} options={[{ value: "radius", label: "Radius" }, { value: "velocity", label: "dr/dt" }, { value: "confidence", label: "Conf." }]} />} />}
            </Panel>
          )}
        </div>

        <div className="vw-col">
          <Panel title="Processing" eyebrow="Telemetry">
            {live.job ? (<>
              <div className="row-between"><StatusPill state={live.job.status} /><span className="data-s subtle">{live.transport !== "idle" ? live.transport : ""}</span></div>
              <Progress value={live.job.progress} label="Frames" detail={`${live.latest?.frames_analyzed ?? live.job.frames_processed} analysed`} state={live.job.status} />
              <Kv rows={[["Elapsed", duration(live.latest?.elapsed_s ?? live.job.duration_s ?? null)], ["Latest frame", live.latest?.frame_index ?? "—"],
                ["Rate", live.latest && live.latest.elapsed_s > 0 ? `${fmt(live.latest.frames_analyzed / live.latest.elapsed_s, 1)} frames/s` : "—"], ["Message", live.job.error ?? live.job.message]]} />
              {isLive && <Button size="sm" variant="danger" onClick={() => api.cancelJob(live.job!.id).then(() => notify("info", "Cancellation requested")).catch((e) => notify("bad", "Cancel failed", errorMessage(e)))}>Cancel</Button>}
              {live.error && <Alert tone="warn" title="Telemetry interrupted">{live.error}</Alert>}
            </>) : b.completed ? <Kv rows={[["Last run", <StatusPill key="s" state="completed" />], ["Frames", b.completed.frames_processed], ["Duration", duration(jobSeconds(b.completed))]]} />
              : <p className="body-s subtle">No analysis has run for this experiment.</p>}
          </Panel>
          <Panel title={`Frame ${frame}`} eyebrow="Current frame">
            {isLive ? (liveByFrame.get(frame) ? <Kv rows={[["Status", <StatusPill key="s" state={liveByFrame.get(frame)!.status} />], ["Radius", liveByFrame.get(frame)!.radius_mm != null ? `${fmt(liveByFrame.get(frame)!.radius_mm, 2)} mm` : `${fmt(liveByFrame.get(frame)!.equivalent_radius_px, 1)} px`], ["Confidence", fmt(liveByFrame.get(frame)!.confidence, 2)]]} /> : <p className="body-s subtle">Not analysed yet.</p>)
              : m && m.frame_index === frame ? (() => {
                const [rv, rs] = fmtSigma(u === "mm" ? m.radius_mm : m.equivalent_radius_px, u === "mm" ? m.radius_sigma_mm : m.equivalent_radius_sigma_px);
                const [lv, ls] = fmtSigma(u === "mm" ? m.limb_radius_mm : m.limb_radius_px, u === "mm" ? m.limb_radius_sigma_mm : m.limb_radius_sigma_px);
                const [vv, vs] = fmtSigma(u === "mm" ? m.expansion_velocity_mm_s : m.expansion_velocity_px_s, u === "mm" ? m.expansion_velocity_sigma_mm_s : m.expansion_velocity_sigma_px_s);
                return <Kv rows={[["Status", <StatusPill key="s" state={m.status} />], ["Time", `${fmt(m.timestamp_s, 4)} s`], ["Equivalent radius", `${rv}${rs ? ` ± ${rs}` : ""} ${u}`],
                  ["Limb radius", m.limb_fit_ok ? `${lv}${ls ? ` ± ${ls}` : ""} ${u}` : m.limb_radius_px != null ? "fit rejected" : "—"], ["dr/dt", vv !== "—" ? `${vv}${vs ? ` ± ${vs}` : ""} ${u}/s` : "—"],
                  ["Circularity", fmt(m.circularity, 3)], ["Confidence", fmt(m.confidence, 2)], ["Warnings", m.warnings.join("; ") || "none"]]} />;
              })() : r ? <p className="body-s subtle">Frame not analysed (frame step {r.config.frame_step ?? 1}). Step with the arrows to an analysed frame.</p> : <p className="body-s subtle">Run an analysis to see measurements.</p>}
          </Panel>
          {r && !isLive && <Panel title="Validation" eyebrow={`${r.issues.length} issues`}><IssueList issues={r.issues} limit={5} /></Panel>}
        </div>
      </div>
    </div>
  );
}
