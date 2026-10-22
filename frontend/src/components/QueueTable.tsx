import type { Column, RecordRow } from "../types";
import { age, cell } from "../format";
import { StatusBadge } from "./StatusBadge";

type Props = {
  columns: Column[];
  rows: RecordRow[];
  loading: boolean;
  error: string | null;
  selectedId: number | null;
  onOpen: (id: number) => void;
  onRetry: () => void;
};

export function QueueTable({ columns, rows, loading, error, selectedId, onOpen, onRetry }: Props) {
  if (error)
    return (
      <div className="state state-error" role="alert">
        Couldn't load the queue: {error} <button className="btn btn-ghost" onClick={onRetry}>Retry</button>
      </div>
    );
  if (loading && rows.length === 0) return <div className="state">Loading queue…</div>;
  if (rows.length === 0) return <div className="state">No requests match the current search and filter.</div>;
  return (
    <div className="table-wrap">
      <table className="queue">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.kind === "money" ? "num" : undefined}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              className={r.id === selectedId ? "selected" : undefined}
              onClick={() => onOpen(r.id)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen(r.id)}
              tabIndex={0}
              data-testid={`row-${r.ref}`}
            >
              {columns.map((c) => (
                <td key={c.key} className={c.kind === "money" ? "num" : c.kind === "text" || c.kind === "list" ? "wrap" : undefined}>
                  {c.kind === "status" ? (
                    <StatusBadge status={r.status} />
                  ) : c.kind === "datetime" ? (
                    <span title={cell(c.kind, r[c.key])}>{age(String(r[c.key]))}</span>
                  ) : c.key === "ref" ? (
                    <span className="mono">{String(r.ref)}</span>
                  ) : (
                    cell(c.kind, r[c.key])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
