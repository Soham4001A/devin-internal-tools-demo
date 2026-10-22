export type Persona = { id: string; name: string; role: string; label: string; can_decide: boolean };
export type Column = { key: string; label: string; kind: "text" | "money" | "datetime" | "status" };
export type Action = { key: string; label: string; to_status: string; from_statuses: string[]; requires_reason: boolean };
export type ToolConfig = {
  key: string;
  name: string;
  record_label: string;
  statuses: string[];
  columns: Column[];
  detail_fields: Column[];
  actions: Action[];
};
export type RecordRow = { id: number; ref: string; status: string; submitted_at: string; updated_at: string } & Record<string, unknown>;
export type HistoryEvent = {
  id: number;
  action: string;
  actor: string;
  actor_role: string;
  reason: string | null;
  from_status: string | null;
  to_status: string | null;
  created_at: string;
};
export type Detail = { record: RecordRow; history: HistoryEvent[] };
export type Summary = { total: number; counts: Record<string, number>; pending_amount_usd: number; overdue_pending: number; overdue_hours: number };
