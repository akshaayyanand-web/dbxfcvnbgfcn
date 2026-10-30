// The application frame: seven navigation categories, the experiment context bar, live processing status,
// notifications, the workspace menu and toasts. Every page renders inside <Outlet />.
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Bell, Menu, Settings2, X } from "lucide-react";
import { StatusPill } from "../design-system";
import { api } from "../services/api";
import { useApp } from "../store/app";
import { usePolling } from "../hooks";
import { ago, DATA_CLASS_LABEL, setDateMode } from "../lib/format";
import type { ProcessingJob } from "../types/api";

export interface NavCategory { id: string; label: string; to: string; pages: { to: string; label: string }[] }

export const NAV: NavCategory[] = [
  { id: "mission", label: "Mission Control", to: "/dashboard", pages: [{ to: "/dashboard", label: "Mission Control" }, { to: "/present", label: "Guided demo" }] },
  { id: "experiments", label: "Experiments", to: "/experiments", pages: [{ to: "/experiments", label: "Experiments" }] },
  { id: "video", label: "Video Intelligence", to: "/video-analysis", pages: [{ to: "/video-analysis", label: "Video analysis" }] },
  { id: "analytics", label: "Analytics", to: "/analytics/flame", pages: [{ to: "/analytics/flame", label: "Flame analytics" }, { to: "/comparison", label: "Comparison" }] },
  { id: "prediction", label: "Prediction", to: "/prediction", pages: [{ to: "/prediction", label: "Predictive intelligence" }, { to: "/models", label: "Models" }] },
  { id: "data", label: "Data & Reports", to: "/datasets", pages: [{ to: "/datasets", label: "Datasets" }, { to: "/reports", label: "Reports" }] },
  { id: "system", label: "System", to: "/system", pages: [{ to: "/system", label: "System health" }, { to: "/settings", label: "Settings" }] },
];

export function categoryFor(path: string): NavCategory | undefined {
  return NAV.find((c) => c.pages.some((p) => path === p.to || path.startsWith(`${p.to}/`)));
}

function useJobWatcher() {
  const notify = useApp((s) => s.notify);
  const active = usePolling(() => api.jobs(undefined, 50).then((js) => js.filter((j) => j.status === "queued" || j.status === "processing")), 3000);
  const prev = useRef<Map<string, ProcessingJob>>(new Map());
  useEffect(() => {
    if (!active.data) return;
    const now = new Map(active.data.map((j) => [j.id, j]));
    for (const [id] of prev.current) {
      if (!now.has(id)) {
        api.job(id).then((j) => {
          if (j.status === "completed") notify("ok", "Analysis completed", `${j.frames_processed} frames analysed${j.duration_s ? ` in ${j.duration_s.toFixed(1)} s` : ""}.`);
          else if (j.status === "failed") notify("bad", "Analysis failed", j.error ?? j.message);
          else if (j.status === "cancelled") notify("info", "Analysis cancelled");
        }).catch(() => undefined);
      }
    }
    prev.current = now;
  }, [active.data, notify]);
  return active;
}

export default function AppShell() {
  const loc = useLocation();
  const nav = useNavigate();
  const { experimentId, setExperiment, notices, toasts, dismissToast, markAllRead, setTheme, theme } = useApp();
  const [drawer, setDrawer] = useState<"none" | "notices" | "nav">("none");
  const [menu, setMenu] = useState(false);
  const health = usePolling(() => api.health(), 15000);
  const experiments = usePolling(() => api.experiments({ limit: 500 }), 10000);
  const settings = usePolling(() => api.settings(), 60000);
  const active = useJobWatcher();
  const cat = categoryFor(loc.pathname);
  const unread = notices.filter((n) => !n.read).length;
  const current = experiments.data?.find((e) => e.id === experimentId);
  const workspace = settings.data?.settings.workspace_name ?? "Local workspace";

  useEffect(() => { setTheme(theme); /* apply persisted theme on load */ }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (settings.data) setDateMode(settings.data.settings.date_format); }, [settings.data]);
  useEffect(() => { setDrawer("none"); setMenu(false); document.getElementById("main")?.focus(); }, [loc.pathname]);
  useEffect(() => {
    if (experiments.data && experimentId && !experiments.data.some((e) => e.id === experimentId)) setExperiment(null);
  }, [experiments.data, experimentId, setExperiment]);
  useEffect(() => {
    const title = cat?.pages.find((p) => loc.pathname.startsWith(p.to))?.label ?? "Flame in Freefall";
    document.title = `${title} · Flame in Freefall`;
  }, [loc.pathname, cat]);

  const apiDown = !!health.error && !health.data;
  const nActive = active.data?.length ?? 0;

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="topbar-row">
          <button className="fif-icon-btn menu-btn" aria-label="Open navigation" onClick={() => setDrawer("nav")}><Menu size={18} /></button>
          <Link to="/dashboard" className="fif-brand"><span className="fif-brand-mark" aria-hidden />Flame in Freefall</Link>
          <nav className="fif-nav" aria-label="Main">
            {NAV.map((c) => <NavLink key={c.id} to={c.to} aria-current={cat?.id === c.id ? "page" : undefined}>{c.label}</NavLink>)}
          </nav>
          <div className="topbar-end">
            <button className="fif-icon-btn" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} onClick={() => setDrawer("notices")}>
              <Bell size={17} />{unread > 0 && <span className="fif-badge">{unread}</span>}
            </button>
            <div className="rel">
              <button className="fif-icon-btn" aria-label="Workspace menu" aria-expanded={menu} onClick={() => setMenu((m) => !m)}><Settings2 size={17} /></button>
              {menu && (
                <div className="menu" role="menu">
                  <div style={{ padding: "6px 10px 10px" }}>
                    <div className="title">{workspace}</div>
                    <div className="body-s subtle">Local workspace · no sign-in. Writes {settings.data?.server.auth_required_for_writes ? "require an API key (set in Settings)" : "are open on this server"}.</div>
                  </div>
                  <hr className="divider" />
                  <Link className="menu-item" to="/settings" role="menuitem">Settings</Link>
                  <Link className="menu-item" to="/system" role="menuitem">System health</Link>
                  <Link className="menu-item" to="/present" role="menuitem">Guided demonstration</Link>
                  <button className="menu-item" role="menuitem" onClick={() => setTheme(theme === "dark" ? "light" : theme === "light" ? "system" : "dark")}>
                    Theme: {theme} (switch)
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="contextbar">
          <div className="ctx-select">
            <label className="fif-label" htmlFor="ctx-exp">Experiment</label>
            <select id="ctx-exp" value={experimentId ?? ""} onChange={(e) => setExperiment(e.target.value || null)} disabled={!experiments.data}>
              <option value="">{experiments.data ? (experiments.data.length ? "None selected" : "No experiments yet") : "Loading…"}</option>
              {experiments.data?.map((e) => <option key={e.id} value={e.id}>{e.name} · {DATA_CLASS_LABEL[e.data_class]}</option>)}
            </select>
            {current && <StatusPill state={current.status} />}
            {current && <Link className="body-s" to={`/experiments/${current.id}`}>Open</Link>}
          </div>
          <div className="ctx-meta">
            {apiDown ? <StatusPill state="unavailable">API offline</StatusPill>
              : nActive > 0 ? <button className="fif-icon-btn" style={{ all: "unset", cursor: "pointer" }} onClick={() => nav("/system")} aria-label={`${nActive} analyses running, open system page`}><StatusPill state="processing">{nActive} running</StatusPill></button>
              : health.data ? <StatusPill state="operational">API {health.data.api_version}</StatusPill> : <StatusPill state="queued">Connecting</StatusPill>}
          </div>
        </div>
      </header>

      {cat && cat.pages.length > 1 && (
        <div className="subnav-row">
          <nav className="fif-subnav" aria-label={`${cat.label} pages`}>
            {cat.pages.map((p) => <NavLink key={p.to} to={p.to} end>{p.label}</NavLink>)}
          </nav>
        </div>
      )}

      <main className="main" id="main" tabIndex={-1}>
        {apiDown && (
          <div style={{ marginBottom: 16 }} className="fif-alert fif-alert-bad" role="alert">
            <span className="fif-alert-mark">Error</span>
            <span className="fif-alert-title">The analysis server is not reachable.</span>
            <span className="fif-alert-body">Start it with <code>uvicorn backend.app:app</code>. Pages show their last loaded data until it is back; nothing shown here is simulated.</span>
          </div>
        )}
        <Outlet />
      </main>

      <footer className="footer">
        <span>Flame in Freefall · measured, image-derived, calculated and predicted quantities are labelled separately.</span>
        <span>NASA PSI data are CC0; no NASA endorsement is implied.</span>
      </footer>

      {drawer !== "none" && <div className="drawer-backdrop" onClick={() => setDrawer("none")} />}
      {drawer === "notices" && (
        <aside className="drawer" aria-label="Notifications">
          <div className="drawer-head">
            <h2 className="title">Notifications</h2>
            <div className="row">
              <button className="fif-btn fif-btn-ghost fif-btn-sm" onClick={markAllRead} disabled={!unread}>Mark read</button>
              <button className="fif-icon-btn" aria-label="Close" onClick={() => setDrawer("none")}><X size={18} /></button>
            </div>
          </div>
          <div className="drawer-body">
            {notices.length === 0 ? <p className="body-s subtle">No notifications in this session. Job completions, failures and saved items appear here.</p>
              : notices.map((n) => (
                <div key={n.id} className={`notice notice-${n.tone}${n.read ? "" : " is-unread"}`}>
                  <span className="notice-dot" aria-hidden />
                  <div><div className="title" style={{ fontSize: 15 }}>{n.title}</div>{n.body && <div className="body-s muted">{n.body}</div>}<div className="data-s subtle">{ago(n.time)}</div></div>
                </div>
              ))}
          </div>
        </aside>
      )}
      {drawer === "nav" && (
        <aside className="drawer drawer-left" aria-label="Navigation">
          <div className="drawer-head"><span className="fif-brand"><span className="fif-brand-mark" aria-hidden />Flame in Freefall</span>
            <button className="fif-icon-btn" aria-label="Close" onClick={() => setDrawer("none")}><X size={18} /></button></div>
          <nav className="drawer-body mobile-nav" aria-label="Main">
            {NAV.map((c) => (
              <div key={c.id} className="group">
                <div className="fif-label" style={{ padding: "0 14px 4px" }}>{c.label}</div>
                {c.pages.map((p) => <NavLink key={p.to} to={p.to} end>{p.label}</NavLink>)}
              </div>
            ))}
          </nav>
        </aside>
      )}

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast${t.tone === "bad" ? " toast-bad" : ""}`} role={t.tone === "bad" ? "alert" : "status"}>
            <div><strong>{t.title}</strong>{t.body && <div style={{ opacity: 0.85 }}>{t.body}</div>}</div>
            <button className="fif-icon-btn" aria-label="Dismiss" onClick={() => dismissToast(t.id)}><X size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
