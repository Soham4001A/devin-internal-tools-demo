import { useEffect } from "react";
import type { Detail, Persona, ToolConfig } from "../types";
import { age, cell } from "../format";
import { StatusBadge } from "./StatusBadge";
import { DecisionPanel } from "./DecisionPanel";
import { HistoryTimeline } from "./HistoryTimeline";

type Props = {
  tool: ToolConfig;
  detail: Detail | null;
  loading: boolean;
  error: string | null;
  persona: Persona | undefined;
  onClose: () => void;
  onDecide: (action: string, reason: string) => Promise<void>;
};

export function RecordDrawer({ tool, detail, loading, error, persona, onClose, onDecide }: Props) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const r = detail?.record;
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`${tool.record_label} detail`}>
        <header className="drawer-head">
          <div>
            <div className="muted small">{tool.record_label}</div>
            <h2 className="mono">{r?.ref ?? "…"}</h2>
          </div>
          <div className="drawer-head-right">
            {r && <StatusBadge status={r.status} />}
            <button className="btn btn-ghost" onClick={onClose} aria-label="Close">✕</button>
          </div>
        </header>
        {error && <div className="state state-error" role="alert">{error}</div>}
        {loading && !r && <div className="state">Loading…</div>}
        {r && (
          <div className="drawer-body">
            <dl className="fields">
              {tool.detail_fields.map((f) => (
                <div key={f.key}>
                  <dt>{f.label}</dt>
                  <dd className={f.kind === "money" ? "amount" : undefined}>
                    {cell(f.kind, r[f.key])}
                    {f.kind === "datetime" && <span className="muted small"> ({age(String(r[f.key]))})</span>}
                  </dd>
                </div>
              ))}
            </dl>
            <section>
              <h3>Decision</h3>
              <DecisionPanel key={r.id} actions={tool.actions} record={r} persona={persona} onDecide={onDecide} />
            </section>
            <section>
              <h3>History</h3>
              <HistoryTimeline events={detail.history} />
            </section>
          </div>
        )}
      </aside>
    </>
  );
}
