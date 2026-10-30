// Global client state: current experiment context, notifications, theme and unit preference.
import { create } from "zustand";

export type Tone = "info" | "ok" | "warn" | "bad";
export interface Notice { id: number; tone: Tone; title: string; body?: string; time: string; read: boolean }
export type ThemePref = "system" | "light" | "dark";

const read = (k: string): string | null => { try { return window.localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string | null) => { try { if (v === null) window.localStorage.removeItem(k); else window.localStorage.setItem(k, v); } catch { /* storage blocked */ } };

interface AppState {
  experimentId: string | null;
  setExperiment: (id: string | null) => void;
  notices: Notice[];
  toasts: Notice[];
  notify: (tone: Tone, title: string, body?: string) => void;
  dismissToast: (id: number) => void;
  markAllRead: () => void;
  theme: ThemePref;
  setTheme: (t: ThemePref) => void;
  units: "mm" | "px";
  setUnits: (u: "mm" | "px") => void;
  comparison: string[];
  toggleComparison: (id: string) => void;
  setComparison: (ids: string[]) => void;
}

let seq = 0;

export const useApp = create<AppState>((set, get) => ({
  experimentId: read("fif.experiment"),
  setExperiment: (id) => { write("fif.experiment", id); set({ experimentId: id }); },
  notices: [],
  toasts: [],
  notify: (tone, title, body) => {
    const n: Notice = { id: ++seq, tone, title, body, time: new Date().toISOString(), read: false };
    set({ notices: [n, ...get().notices].slice(0, 100), toasts: [...get().toasts, n] });
    window.setTimeout(() => get().dismissToast(n.id), tone === "bad" ? 9000 : 5000);
  },
  dismissToast: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
  markAllRead: () => set({ notices: get().notices.map((n) => ({ ...n, read: true })) }),
  theme: (read("fif.theme") as ThemePref) || "system",
  setTheme: (t) => {
    write("fif.theme", t);
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    set({ theme: t });
  },
  units: (read("fif.units") as "mm" | "px") || "mm",
  setUnits: (u) => { write("fif.units", u); set({ units: u }); },
  comparison: [],
  toggleComparison: (id) => {
    const c = get().comparison;
    set({ comparison: c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-6) });
  },
  setComparison: (ids) => set({ comparison: ids }),
}));
