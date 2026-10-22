import type { Detail, Persona, Summary, ToolConfig, RecordRow } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, persona: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Demo-Persona": persona, ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  personas: () => req<{ personas: Persona[]; default: string }>("/api/personas", ""),
  tool: (tool: string) => req<ToolConfig>(`/api/tools/${tool}`, ""),
  list: (tool: string, persona: string, q: string, status: string, overdue = false) =>
    req<{ items: RecordRow[] }>(
      `/api/tools/${tool}/records?${new URLSearchParams({ q, status, ...(overdue ? { overdue: "true" } : {}) })}`,
      persona,
    ),
  summary: (tool: string, persona: string) => req<Summary>(`/api/tools/${tool}/summary`, persona),
  detail: (tool: string, persona: string, id: number) => req<Detail>(`/api/tools/${tool}/records/${id}`, persona),
  decide: (tool: string, persona: string, id: number, action: string, reason: string) =>
    req<Detail>(`/api/tools/${tool}/records/${id}/decision`, persona, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    }),
  reset: (tool: string) => req<{ ok: boolean }>(`/api/demo/reset?tool=${tool}`, "", { method: "POST" }),
};
