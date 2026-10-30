// Frame viewer: server-decoded JPEG frames (the same decoder and image-sequence scaling the analysis used) with an
// SVG overlay in full-resolution pixel coordinates. Supports transport controls, playback and calibration clicks.
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { api } from "../services/api";
import { fmt } from "../lib/format";
import type { VideoMetadata } from "../types/api";

export type Layer = "contour" | "centroid" | "equivalent" | "limb" | "grid" | "hud";
export const LAYERS: { id: Layer; label: string; color: string }[] = [
  { id: "contour", label: "Contour", color: "var(--overlay-contour)" },
  { id: "limb", label: "Shell limb fit", color: "var(--overlay-limb)" },
  { id: "equivalent", label: "Equivalent circle", color: "var(--overlay-warn)" },
  { id: "centroid", label: "Centroid", color: "var(--overlay-centroid)" },
  { id: "grid", label: "Pixel grid", color: "#8f97a3" },
  { id: "hud", label: "Readouts", color: "#eef1f5" },
];

export interface FrameOverlay {
  status?: string; confidence?: number | null; timestamp_s?: number | null;
  contour?: [number, number][] | null; centroid?: [number, number] | null; equivalentRadius?: number | null;
  limb?: { cx: number; cy: number; r: number; ok: boolean } | null; radiusText?: string | null;
}

export default function VideoViewer({ experimentId, media, index, onIndex, overlay, layers, step = 1, calibrating, calPoints = [], onCalClick, maxIndex }: {
  experimentId: string; media: VideoMetadata; index: number; onIndex: (i: number) => void; overlay?: FrameOverlay | null;
  layers: Set<Layer>; step?: number; calibrating?: boolean; calPoints?: [number, number][]; onCalClick?: (p: [number, number]) => void; maxIndex?: number;
}) {
  const last = Math.max(0, (maxIndex ?? media.reported_frame_count - 1));
  const [playing, setPlaying] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const W = media.width, H = media.height;
  const src = api.frameUrl(experimentId, index, 1400);

  useEffect(() => { setLoaded(false); setFailed(null); }, [src]);
  useEffect(() => {
    if (!playing || !loaded) return;
    const t = window.setTimeout(() => { if (index + step > last) setPlaying(false); else onIndex(index + step); }, 120);
    return () => window.clearTimeout(t);
  }, [playing, loaded, index, step, last, onIndex]);

  const go = (i: number) => onIndex(Math.max(0, Math.min(last, i)));
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); go(index + step); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(index - step); }
    else if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
  };
  const click = (e: MouseEvent<SVGSVGElement>) => {
    if (!calibrating || !onCalClick || !svg.current) return;
    const pt = svg.current.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const m = svg.current.getScreenCTM();
    if (!m) return;
    const p = pt.matrixTransform(m.inverse());
    if (p.x >= 0 && p.y >= 0 && p.x <= W && p.y <= H) onCalClick([p.x, p.y]);
  };
  const sw = Math.max(1.5, W / 500);
  const time = overlay?.timestamp_s ?? media.frame_times_s?.[index] ?? (media.nominal_fps ? index / media.nominal_fps : null);

  return (
    <div className="stack-s">
      <div className="viewer" style={{ aspectRatio: `${W} / ${H}` }} tabIndex={0} onKeyDown={onKey} aria-label={`Frame ${index} of ${last}. Left and right arrows step, space plays.`}>
        {failed ? <div className="viewer-msg">Frame {index} could not be decoded: {failed}</div>
          : <img src={src} alt={`Frame ${index}`} onLoad={() => setLoaded(true)} onError={() => { setFailed("the server returned an error for this frame"); setPlaying(false); }} />}
        {!loaded && !failed && <div className="viewer-msg">Decoding frame {index}…</div>}
        <svg ref={svg} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" onClick={click}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", cursor: calibrating ? "crosshair" : undefined }} aria-hidden>
          {layers.has("grid") && Array.from({ length: 9 }, (_, i) => (
            <g key={i} stroke="#8f97a3" strokeOpacity={0.35} strokeWidth={sw / 2}>
              <line x1={(W * (i + 1)) / 10} y1={0} x2={(W * (i + 1)) / 10} y2={H} /><line x1={0} y1={(H * (i + 1)) / 10} x2={W} y2={(H * (i + 1)) / 10} />
            </g>
          ))}
          {overlay && layers.has("contour") && overlay.contour && overlay.contour.length > 2 && (
            <polygon points={overlay.contour.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" stroke="var(--overlay-contour)" strokeWidth={sw} />
          )}
          {overlay && layers.has("equivalent") && overlay.centroid && overlay.equivalentRadius != null && (
            <circle cx={overlay.centroid[0]} cy={overlay.centroid[1]} r={overlay.equivalentRadius} fill="none" stroke="var(--overlay-warn)" strokeWidth={sw} strokeDasharray={`${sw * 4} ${sw * 3}`} />
          )}
          {overlay && layers.has("limb") && overlay.limb && (
            <circle cx={overlay.limb.cx} cy={overlay.limb.cy} r={overlay.limb.r} fill="none" stroke="var(--overlay-limb)" strokeWidth={sw * 1.3} strokeOpacity={overlay.limb.ok ? 1 : 0.45} strokeDasharray={overlay.limb.ok ? undefined : `${sw * 2} ${sw * 2}`} />
          )}
          {overlay && layers.has("centroid") && overlay.centroid && (
            <g stroke="var(--overlay-centroid)" strokeWidth={sw}>
              <line x1={overlay.centroid[0] - sw * 6} y1={overlay.centroid[1]} x2={overlay.centroid[0] + sw * 6} y2={overlay.centroid[1]} />
              <line x1={overlay.centroid[0]} y1={overlay.centroid[1] - sw * 6} x2={overlay.centroid[0]} y2={overlay.centroid[1] + sw * 6} />
            </g>
          )}
          {calPoints.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={sw * 4} fill="var(--lime-400)" stroke="#050608" strokeWidth={sw / 2} />)}
          {calPoints.length === 2 && <line x1={calPoints[0][0]} y1={calPoints[0][1]} x2={calPoints[1][0]} y2={calPoints[1][1]} stroke="var(--lime-400)" strokeWidth={sw} />}
        </svg>
        {layers.has("hud") && (
          <div className="viewer-hud">
            <span>frame {index}</span>
            {time != null && <span>t = {fmt(time, 3)} s</span>}
            {overlay?.status && <span>{overlay.status.replace(/_/g, " ")}</span>}
            {overlay?.confidence != null && <span>conf {fmt(overlay.confidence, 2)}</span>}
            {overlay?.radiusText && <span>{overlay.radiusText}</span>}
            {calibrating && <span style={{ background: "var(--lime-400)", color: "#0d1116" }}>Calibration: click two points</span>}
          </div>
        )}
      </div>
      <div className="transport">
        <button className="fif-icon-btn" aria-label="First frame" onClick={() => go(0)}><ChevronFirst size={16} /></button>
        <button className="fif-icon-btn" aria-label="Previous frame" onClick={() => go(index - step)}><ChevronLeft size={16} /></button>
        <button className="fif-icon-btn" aria-label={playing ? "Pause" : "Play"} aria-pressed={playing} onClick={() => setPlaying((p) => !p)}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
        <button className="fif-icon-btn" aria-label="Next frame" onClick={() => go(index + step)}><ChevronRight size={16} /></button>
        <button className="fif-icon-btn" aria-label="Last frame" onClick={() => go(last)}><ChevronLast size={16} /></button>
        <input type="range" min={0} max={last} step={step} value={index} onChange={(e) => go(Number(e.target.value))} aria-label="Frame position" />
        <span className="readout">{index} / {last}{time != null ? ` · ${fmt(time, 3)} s` : ""}</span>
      </div>
    </div>
  );
}
