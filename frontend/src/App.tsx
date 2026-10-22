import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { TOOL_UIS, toolForPath, type ToolUi } from "./tools";
import type { Detail, Persona, RecordRow, Summary, ToolConfig } from "./types";
import { cap } from "./format";
import { SummaryBar } from "./components/SummaryBar";
import { QueueTable } from "./components/QueueTable";
import { RecordDrawer } from "./components/RecordDrawer";

const PERSONA_KEY = "ops-workbench.demo-persona"; // UI preference only; permissions are enforced server-side.

export default function App() {
  const [ui, setUi] = useState<ToolUi>(() => toolForPath(window.location.pathname));
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<string>(() => localStorage.getItem(PERSONA_KEY) ?? "reviewer");
  const [resetCount, setResetCount] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const persona = personas.find((p) => p.id === personaId);

  useEffect(() => {
    api.personas().then((r) => setPersonas(r.personas)).catch(() => setPersonas([]));
  }, []);
  useEffect(() => localStorage.setItem(PERSONA_KEY, personaId), [personaId]);
  useEffect(() => {
    const onPop = () => setUi(toolForPath(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    document.title = `${ui.navLabel} · Ops Workbench (demo)`;
  }, [ui]);

  const notify = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const navigate = (t: ToolUi) => {
    if (t.key === ui.key) return;
    window.history.pushState(null, "", t.path);
    setUi(t);
  };

  const reset = async () => {
    if (!confirm(`Reset ${ui.navLabel}? All decisions in this tool will be replaced by the original synthetic fixtures.`)) return;
    await api.reset(ui.key);
    setResetCount((n) => n + 1);
    notify(`${ui.navLabel} demo data reset`);
  };

  return (
    <div className="shell">
      <nav className="nav" aria-label="Tools">
        <div className="brand">
          <span className="brand-mark">◆</span> Ops Workbench
        </div>
        <div className="nav-section">Tools</div>
        {TOOL_UIS.map((t) => (
          <a
            key={t.key}
            className={`nav-item ${t.key === ui.key ? "active" : ""}`}
            href={t.path}
            aria-current={t.key === ui.key ? "page" : undefined}
            onClick={(e) => {
              e.preventDefault();
              navigate(t);
            }}
          >
            {t.navLabel}
          </a>
        ))}
        <div className="nav-foot">
          <div className="nav-section">Demo persona</div>
          <select aria-label="Demo persona" className="persona" value={personaId} onChange={(e) => setPersonaId(e.target.value)}>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
          <div className="muted-nav small">
            {persona ? `${cap(persona.role)} · ${persona.can_decide ? "can decide" : "view only"}` : ""}
          </div>
          <button className="btn btn-nav" onClick={reset}>Reset demo data</button>
        </div>
      </nav>
      {/* Keyed by tool: search, filters, selection and drawer state never carry over between tools. */}
      <ToolView key={`${ui.key}:${resetCount}`} ui={ui} personaId={personaId} persona={persona} notify={notify} />
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

type ToolViewProps = { ui: ToolUi; personaId: string; persona: Persona | undefined; notify: (msg: string) => void };

function ToolView({ ui, personaId, persona, notify }: ToolViewProps) {
  const toolKey = ui.key;
  const [tool, setTool] = useState<ToolConfig | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [rows, setRows] = useState<RecordRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    api.tool(toolKey).then(setTool).catch((e) => setError(e.message));
  }, [toolKey]);

  const overdueEnabled = tool?.features.overdue_filter ?? false;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, s] = await Promise.all([
        api.list(toolKey, personaId, q, status, overdue && overdueEnabled),
        api.summary(toolKey, personaId),
      ]);
      setRows(list.items);
      setSummary(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [toolKey, personaId, q, status, overdue, overdueEnabled]);

  useEffect(() => {
    const t = setTimeout(refresh, 150);
    return () => clearTimeout(t);
  }, [refresh]);

  useEffect(() => {
    if (openId == null) return;
    setDetailLoading(true);
    setDetailError(null);
    api
      .detail(toolKey, personaId, openId)
      .then(setDetail)
      .catch((e) => setDetailError(e.message))
      .finally(() => setDetailLoading(false));
  }, [openId, toolKey, personaId]);

  const close = useCallback(() => {
    setOpenId(null);
    setDetail(null);
  }, []);

  const decide = async (action: string, reason: string) => {
    if (openId == null) return;
    const d = await api.decide(toolKey, personaId, openId, action, reason);
    setDetail(d);
    notify(`${d.record.ref} ${d.record.status}`);
    refresh();
  };

  return (
    <>
      <main className="main" data-tool={toolKey}>
        <div className="banner" role="note">
          <strong>Demo environment</strong> — {ui.banner} Personas are demo-only (no real sign-in).
        </div>
        <header className="page-head">
          <div>
            <h1>{ui.title}</h1>
            <p className="muted">{ui.subtitle}</p>
          </div>
        </header>
        <SummaryBar
          summary={summary}
          statuses={tool?.statuses ?? []}
          showOverdue={overdueEnabled}
          showValue={tool?.features.value_summary ?? false}
          totalLabel={ui.totalLabel}
        />
        <div className="toolbar">
          <input
            type="search"
            className="search"
            placeholder={ui.searchPlaceholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search"
          />
          <select className="filter" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
            <option value="">All statuses</option>
            {tool?.statuses.map((s) => (
              <option key={s} value={s}>{cap(s)}</option>
            ))}
          </select>
          {overdueEnabled && (
            <label className="toggle">
              <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} />
              Over 48 hours
            </label>
          )}
          <span className="muted small">
            {loading ? "Refreshing…" : `${rows.length} shown${overdue && overdueEnabled ? " · pending over 48h, oldest first" : ""}`}
          </span>
        </div>
        <QueueTable
          columns={tool?.columns ?? []}
          rows={rows}
          loading={loading || !tool}
          error={error}
          selectedId={openId}
          onOpen={setOpenId}
          onRetry={refresh}
        />
      </main>
      {openId != null && tool && (
        <RecordDrawer
          tool={tool}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          persona={persona}
          onClose={close}
          onDecide={decide}
          reasonPlaceholder={ui.reasonPlaceholder}
          decisionFootnote={ui.decisionFootnote}
        />
      )}
    </>
  );
}
