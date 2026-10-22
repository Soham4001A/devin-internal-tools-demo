import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { TOOL_UIS } from "./tools";
import type { Detail, Persona, RecordRow, Summary, ToolConfig } from "./types";
import { cap } from "./format";
import { SummaryBar } from "./components/SummaryBar";
import { QueueTable } from "./components/QueueTable";
import { RecordDrawer } from "./components/RecordDrawer";

const PERSONA_KEY = "ops-workbench.demo-persona"; // UI preference only; permissions are enforced server-side.

export default function App() {
  const [toolKey] = useState(TOOL_UIS[0].key);
  const ui = TOOL_UIS.find((t) => t.key === toolKey)!;
  const [tool, setTool] = useState<ToolConfig | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<string>(() => localStorage.getItem(PERSONA_KEY) ?? "reviewer");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<RecordRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const persona = personas.find((p) => p.id === personaId);

  useEffect(() => {
    api.personas().then((r) => setPersonas(r.personas)).catch((e) => setError(e.message));
    api.tool(toolKey).then(setTool).catch((e) => setError(e.message));
  }, [toolKey]);

  useEffect(() => localStorage.setItem(PERSONA_KEY, personaId), [personaId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [list, s] = await Promise.all([api.list(toolKey, personaId, q, status), api.summary(toolKey, personaId)]);
      setRows(list.items);
      setSummary(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [toolKey, personaId, q, status]);

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
    setToast(`${d.record.ref} ${d.record.status}`);
    setTimeout(() => setToast(null), 3000);
    refresh();
  };

  const reset = async () => {
    if (!confirm("Reset the demo? All decisions in this tool will be replaced by the original synthetic fixtures.")) return;
    await api.reset(toolKey);
    close();
    refresh();
    setToast("Demo data reset");
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className="shell">
      <nav className="nav">
        <div className="brand">
          <span className="brand-mark">◆</span> Ops Workbench
        </div>
        <div className="nav-section">Tools</div>
        {TOOL_UIS.map((t) => (
          <a key={t.key} className={`nav-item ${t.key === toolKey ? "active" : ""}`} href="#" onClick={(e) => e.preventDefault()}>
            {t.navLabel}
          </a>
        ))}
        <div className="nav-foot">
          <div className="nav-section">Demo persona</div>
          <select
            aria-label="Demo persona"
            className="persona"
            value={personaId}
            onChange={(e) => setPersonaId(e.target.value)}
          >
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
      <main className="main">
        <div className="banner" role="note">
          <strong>Demo environment</strong> — all customers, merchants and amounts are synthetic. Personas are demo-only
          (no real sign-in). Decisions are recorded here only; no refunds or payments are executed.
        </div>
        <header className="page-head">
          <div>
            <h1>{ui.title}</h1>
            <p className="muted">{ui.subtitle}</p>
          </div>
        </header>
        <SummaryBar summary={summary} statuses={tool?.statuses ?? []} />
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
          <span className="muted small">{loading ? "Refreshing…" : `${rows.length} shown`}</span>
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
        />
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
