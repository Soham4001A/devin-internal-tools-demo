import type { Summary } from "../types";
import { cap, money } from "../format";

export function SummaryBar({ summary, statuses }: { summary: Summary | null; statuses: string[] }) {
  return (
    <div className="summary" aria-label="Summary counts">
      <div className="stat">
        <div className="stat-label">Total requests</div>
        <div className="stat-value">{summary ? summary.total : "–"}</div>
      </div>
      {statuses.map((s) => (
        <div className={`stat stat-${s}`} key={s}>
          <div className="stat-label">{cap(s)}</div>
          <div className="stat-value">{summary ? summary.counts[s] ?? 0 : "–"}</div>
        </div>
      ))}
      <div className="stat stat-overdue">
        <div className="stat-label">Pending over {summary?.overdue_hours ?? 48}h</div>
        <div className="stat-value">{summary ? summary.overdue_pending : "–"}</div>
      </div>
      <div className="stat">
        <div className="stat-label">Pending value</div>
        <div className="stat-value">{summary ? money(summary.pending_amount_usd) : "–"}</div>
      </div>
    </div>
  );
}
