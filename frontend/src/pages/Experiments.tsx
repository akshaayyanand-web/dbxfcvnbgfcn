// Experiment library: search, filters, bulk comparison selection, and lifecycle actions.
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Button, ConfirmDialog, DataTable, Field, LoadingBlock, Panel, SelectField, StatusPill, type Column } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import CreateExperiment from "../components/CreateExperiment";
import { DataClassPill, ErrorState, PageHead } from "../components/common";
import { date, fmt } from "../lib/format";
import type { Experiment } from "../types/api";

type Row = Experiment & Record<string, unknown>;

export default function Experiments() {
  const nav = useNavigate();
  const { experimentId, setExperiment, comparison, toggleComparison, notify } = useApp();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [cls, setCls] = useState("");
  const [archived, setArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState<{ exp: Experiment; action: "delete" | "archive" } | null>(null);
  const [busy, setBusy] = useState(false);
  const list = useAsync(() => api.experiments({ includeArchived: archived }), [archived]);

  const rows = useMemo(() => (list.data ?? []).filter((e) =>
    (!q || `${e.name} ${e.description} ${e.fuel_type ?? ""} ${e.dataset_ref ?? ""}`.toLowerCase().includes(q.toLowerCase())) &&
    (!status || e.status === status) && (!cls || e.data_class === cls)) as Row[], [list.data, q, status, cls]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); notify("ok", ok); list.reload(); } catch (e) { notify("bad", "Action failed", errorMessage(e)); } finally { setBusy(false); setConfirm(null); }
  };

  const cols: Column<Row>[] = [
    { key: "cmp", label: <span className="sr-only">Compare</span>, sortable: false, render: (e) => (
      <input type="checkbox" aria-label={`Add ${e.name} to comparison`} checked={comparison.includes(e.id)} onClick={(ev) => ev.stopPropagation()} onChange={() => toggleComparison(e.id)} />) },
    { key: "name", label: "Name", render: (e) => <span className="stack-s" style={{ gap: 2 }}><Link to={`/experiments/${e.id}`} onClick={(ev) => ev.stopPropagation()}>{e.name}</Link>{e.archived && <span className="data-s subtle">archived</span>}</span> },
    { key: "data_class", label: "Source", render: (e) => <DataClassPill exp={e} /> },
    { key: "status", label: "Status", render: (e) => <StatusPill state={e.status} /> },
    { key: "fuel_type", label: "Fuel" },
    { key: "oxygen_fraction", label: "X(O₂)", numeric: true, render: (e) => fmt(e.oxygen_fraction, 3) },
    { key: "calibrated", label: "Calibrated", sortValue: (e) => (e.calibration ? 1 : 0), render: (e) => (e.calibration ? `${fmt(e.calibration.mm_per_px ?? null, 4)} mm/px` : "no") },
    { key: "created_at", label: "Created", render: (e) => date(e.created_at) },
    { key: "actions", label: <span className="sr-only">Actions</span>, sortable: false, render: (e) => (
      <span className="row" onClick={(ev) => ev.stopPropagation()}>
        <Button size="sm" variant="ghost" onClick={() => act(() => api.duplicateExperiment(e.id), `Duplicated ${e.name}`)} disabled={busy}>Duplicate</Button>
        <Button size="sm" variant="ghost" onClick={() => e.archived ? act(() => api.updateExperiment(e.id, { archived: false }), `Restored ${e.name}`) : setConfirm({ exp: e, action: "archive" })} disabled={busy}>{e.archived ? "Restore" : "Archive"}</Button>
        <Button size="sm" variant="danger" onClick={() => setConfirm({ exp: e, action: "delete" })} disabled={busy}>Delete</Button>
      </span>) },
  ];

  return (
    <div className="page">
      <PageHead eyebrow="Experiments" title="Experiment library"
        lede="Every run in this workspace: user uploads, NASA PSI samples and the synthetic demo, each labelled by source. Click a row to put it in context; tick rows to compare."
        actions={<>
          {comparison.length >= 2 && <Button onClick={() => nav("/comparison")}>Compare {comparison.length}</Button>}
          <Button variant="lime" icon={<Plus size={16} />} onClick={() => setCreating(true)}>New experiment</Button>
        </>} />
      <Panel>
        <div className="form-grid">
          <Field label="Search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, fuel, sample id" type="search" />
          <SelectField label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any</option>{["draft", "queued", "processing", "completed", "failed", "cancelled"].map((s) => <option key={s}>{s}</option>)}
          </SelectField>
          <SelectField label="Source" value={cls} onChange={(e) => setCls(e.target.value)}>
            <option value="">Any</option><option value="user">User upload</option><option value="nasa_psi">NASA PSI</option><option value="synthetic">Synthetic demo</option>
          </SelectField>
          <div className="fif-field"><span className="fif-label">Archived</span>
            <label className="fif-check" style={{ height: 40 }}><input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />Include archived</label></div>
        </div>
        {list.error ? <ErrorState error={list.error} onRetry={list.reload} />
          : list.loading && !list.data ? <LoadingBlock rows={6} />
            : <>
              <span className="body-s subtle">{rows.length} of {list.data?.length ?? 0} experiments</span>
              <DataTable columns={cols} rows={rows} rowKey={(e) => e.id} selectedKey={experimentId} onRowClick={(e) => setExperiment(e.id)}
                initialSort={{ key: "created_at", dir: "desc" }} caption="Experiments"
                emptyText={list.data?.length ? "No experiments match these filters." : "No experiments yet. Create one, or run the guided demo to analyse the synthetic sample."} />
            </>}
      </Panel>
      <CreateExperiment open={creating} onClose={() => setCreating(false)} onCreated={list.reload} />
      <ConfirmDialog open={!!confirm} busy={busy} tone={confirm?.action === "delete" ? "danger" : "ink"}
        title={confirm?.action === "delete" ? "Delete experiment?" : "Archive experiment?"}
        body={confirm?.action === "delete" ? `"${confirm.exp.name}" and its analysis jobs are removed from the workspace database. Its predictions and reports are kept but unlinked; result files already in server storage are not deleted.` : `"${confirm?.exp.name}" is hidden from lists but kept; you can restore it.`}
        confirmLabel={confirm?.action === "delete" ? "Delete" : "Archive"} onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && (confirm.action === "delete"
          ? act(async () => { await api.deleteExperiment(confirm.exp.id); if (experimentId === confirm.exp.id) setExperiment(null); }, `Deleted ${confirm.exp.name}`)
          : act(() => api.updateExperiment(confirm.exp.id, { archived: true }), `Archived ${confirm.exp.name}`))} />
    </div>
  );
}
