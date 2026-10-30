import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, jobSocketUrl } from "../services/api";
import type { FrameTelemetry, ProcessingJob } from "../types/api";

export interface AsyncState<T> { data: T | undefined; error: string | null; loading: boolean; reload: () => void }

/** Run an async loader when deps change; exposes loading / error / data and a reload function. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) { setLoading(false); return; }
    let alive = true;
    setLoading(true);
    loader().then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(errorMessage(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

/** Re-run an async loader every `ms` while `active`. */
export function usePolling<T>(loader: () => Promise<T>, ms: number, active = true, deps: unknown[] = []): AsyncState<T> {
  const state = useAsync(loader, deps);
  const { reload } = state;
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(reload, ms);
    return () => window.clearInterval(id);
  }, [active, ms, reload]);
  return state;
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export interface JobTelemetry {
  job: ProcessingJob | undefined;
  events: FrameTelemetry[];
  latest: FrameTelemetry | undefined;
  transport: "websocket" | "polling" | "idle";
  error: string | null;
}

/**
 * Live telemetry for a job: a WebSocket stream when available, otherwise polling of the telemetry endpoint.
 * Events accumulate in order; the job record is refreshed until it reaches a terminal state.
 */
export function useJobTelemetry(jobId: string | null | undefined): JobTelemetry {
  const [events, setEvents] = useState<FrameTelemetry[]>([]);
  const [job, setJob] = useState<ProcessingJob>();
  const [transport, setTransport] = useState<JobTelemetry["transport"]>("idle");
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(-1);

  useEffect(() => {
    setEvents([]); setJob(undefined); setError(null); lastSeq.current = -1;
    if (!jobId) { setTransport("idle"); return; }
    let alive = true;
    let ws: WebSocket | null = null;
    let poll: number | undefined;
    const add = (evs: FrameTelemetry[]) => {
      const fresh = evs.filter((e) => e.seq > lastSeq.current);
      if (!fresh.length) return;
      lastSeq.current = fresh[fresh.length - 1].seq;
      setEvents((prev) => [...prev, ...fresh]);
    };
    const refreshJob = () => api.job(jobId).then((j) => { if (alive) setJob(j); return j; }).catch((e) => { if (alive) setError(errorMessage(e)); });
    const startPolling = () => {
      setTransport("polling");
      const tickPoll = async () => {
        try {
          const t = await (await fetch(`/api/jobs/${jobId}/telemetry?after=${lastSeq.current}&limit=2000`)).json();
          if (!alive) return;
          add(t.events ?? []);
          const j = await refreshJob();
          if (j && TERMINAL.has(j.status)) { window.clearInterval(poll); setTransport("idle"); }
        } catch (e) { if (alive) setError(errorMessage(e)); }
      };
      tickPoll();
      poll = window.setInterval(tickPoll, 700);
    };
    refreshJob().then((j) => {
      if (!alive || !j) return;
      try {
        ws = new WebSocket(jobSocketUrl(jobId));
        setTransport("websocket");
        let opened = false;
        ws.onopen = () => { opened = true; };
        ws.onmessage = (m) => {
          const msg = JSON.parse(m.data);
          if (msg.type === "telemetry") { add(msg.events); setJob((prev) => (prev ? { ...prev, status: msg.status, progress: msg.progress } : prev)); }
          if (msg.type === "done") { refreshJob(); setTransport("idle"); }
          if (msg.type === "error") setError(msg.message);
        };
        ws.onerror = () => { if (!opened && alive) { ws?.close(); startPolling(); } };
        ws.onclose = (ev) => { if (alive && !opened && ev.code !== 1000) startPolling(); };
      } catch { startPolling(); }
    });
    return () => { alive = false; ws?.close(); if (poll) window.clearInterval(poll); };
  }, [jobId]);

  return { job, events, latest: events[events.length - 1], transport, error };
}

/** Media query hook for layouts that reorganise rather than shrink. */
export function useMedia(query: string): boolean {
  const [match, setMatch] = useState(() => typeof window !== "undefined" && window.matchMedia?.(query).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const fn = () => setMatch(mq.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, [query]);
  return !!match;
}
