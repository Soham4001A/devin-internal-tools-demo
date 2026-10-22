import { useState } from "react";
import type { Action, Persona, RecordRow } from "../types";

type Props = {
  actions: Action[];
  record: RecordRow;
  persona: Persona | undefined;
  onDecide: (action: string, reason: string) => Promise<void>;
};

export function DecisionPanel({ actions, record, persona, onDecide }: Props) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const available = actions.filter((a) => a.from_statuses.includes(record.status));

  if (available.length === 0)
    return <div className="note">This request has been decided. Decisions are final in this prototype.</div>;
  if (!persona?.can_decide)
    return (
      <div className="note">
        <strong>{persona?.name ?? "This persona"}</strong> has view-only access. Switch to a reviewer persona to decide.
      </div>
    );

  const submit = async (key: string) => {
    if (reason.trim().length < 3) {
      setError("Enter a decision reason (at least 3 characters).");
      return;
    }
    setBusy(key);
    setError(null);
    try {
      await onDecide(key, reason.trim());
      setReason("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="decision">
      <label htmlFor="reason" className="field-label">Decision reason <span className="req">required</span></label>
      <textarea
        id="reason"
        rows={3}
        value={reason}
        maxLength={1000}
        placeholder="e.g. Duplicate charge confirmed against merchant settlement report"
        onChange={(e) => setReason(e.target.value)}
      />
      {error && <div className="inline-error" role="alert">{error}</div>}
      <div className="decision-actions">
        {available.map((a) => (
          <button
            key={a.key}
            className={`btn ${a.key === "approve" ? "btn-primary" : "btn-danger"}`}
            disabled={busy !== null}
            onClick={() => submit(a.key)}
          >
            {busy === a.key ? "Saving…" : a.label}
          </button>
        ))}
      </div>
      <p className="muted small">Records a decision only. No payment is executed.</p>
    </div>
  );
}
