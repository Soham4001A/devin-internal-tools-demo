import type { HistoryEvent } from "../types";
import { cap, dateTime } from "../format";

const verb: Record<string, string> = { submitted: "Submitted", approve: "Approved", reject: "Rejected" };

export function HistoryTimeline({ events }: { events: HistoryEvent[] }) {
  if (events.length === 0) return <div className="state small">No history yet.</div>;
  return (
    <ol className="timeline" aria-label="Decision history">
      {[...events].reverse().map((e) => (
        <li key={e.id} className={`tl tl-${e.action}`}>
          <div className="tl-head">
            <strong>{verb[e.action] ?? cap(e.action)}</strong>
            <span className="muted"> by {e.actor} · {cap(e.actor_role)}</span>
          </div>
          <time className="muted small" dateTime={e.created_at}>{dateTime(e.created_at)} · {new Date(e.created_at).toISOString().replace("T", " ").slice(0, 19)} UTC</time>
          {e.reason && <p className="tl-reason">“{e.reason}”</p>}
        </li>
      ))}
    </ol>
  );
}
