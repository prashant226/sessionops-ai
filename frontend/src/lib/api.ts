import type {
  AssignmentOut,
  FinalReviewOut,
  GenerateEvent,
  InsightsOut,
  KpiOut,
  NeedsAttentionItem,
  SearchResult,
  SmeDetailOut,
  SmeListItem,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    });
  } catch {
    throw new ApiError("We could not reach the SessionOps AI server. Your existing schedule has not been changed.", 0);
  }
  if (!res.ok) {
    let detail = "Something went wrong. Your existing schedule has not been changed.";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (ops_id: string, password: string) =>
    request<{ token: string; ops_name: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ ops_id, password }),
    }),

  sync: () => request<{ status: string; smes: number; sessions: number }>("/sync", { method: "POST" }),

  kpis: (week_start: string) => request<KpiOut>(`/overview/kpis?week_start=${week_start}`),
  needsAttention: (week_start: string) =>
    request<NeedsAttentionItem[]>(`/overview/needs-attention?week_start=${week_start}`),

  listSessions: (week_start: string) => request<AssignmentOut[]>(`/schedule/sessions?week_start=${week_start}`),
  getAssignment: (id: string) => request<AssignmentOut>(`/schedule/assignments/${id}`),

  async generateDraft(week_start: string, onEvent: (e: GenerateEvent) => void): Promise<void> {
    const res = await fetch(`${BASE_URL}/schedule/generate?week_start=${week_start}`, { method: "POST" });
    if (!res.ok || !res.body) throw new ApiError("Draft generation failed to start.", res.status);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        onEvent(JSON.parse(line));
      }
    }
    if (buffer.trim()) onEvent(JSON.parse(buffer));
  },

  approve: (assignmentId: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/approve`, { method: "POST", body: JSON.stringify({}) }),
  edit: (assignmentId: string, sme_id: string, override_hard_constraint = false) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/edit`, {
      method: "POST",
      body: JSON.stringify({ sme_id, override_hard_constraint }),
    }),
  reject: (assignmentId: string, reason: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  simulateRsvp: (assignmentId: string, rsvp: "ACCEPTED" | "TENTATIVE" | "DECLINED") =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/rsvp/simulate`, {
      method: "POST",
      body: JSON.stringify({ rsvp }),
    }),
  reportDropout: (assignmentId: string, note?: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/dropout`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  sendReplacement: (assignmentId: string, sme_id: string, override_hard_constraint = false) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/replacement/send`, {
      method: "POST",
      body: JSON.stringify({ sme_id, override_hard_constraint }),
    }),
  recheckAvailability: (week_start: string) =>
    request<{ checked: number; new_conflicts: string[] }>(`/schedule/recheck-availability?week_start=${week_start}`, {
      method: "POST",
    }),
  simulateNewConflict: (assignmentId: string) =>
    request<{ status: string }>(`/schedule/assignments/${assignmentId}/simulate-new-conflict`, { method: "POST" }),

  finalReview: (week_start: string) => request<FinalReviewOut>(`/schedule/final-review?week_start=${week_start}`),
  finalize: (week_start: string, force: boolean) =>
    request<{ status: string }>(`/schedule/finalize?week_start=${week_start}`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),

  exceptions: (week_start: string, filter = "All") =>
    request<AssignmentOut[]>(`/exceptions?week_start=${week_start}&filter=${encodeURIComponent(filter)}`),

  insights: (week_start: string) => request<InsightsOut>(`/insights?week_start=${week_start}`),

  smes: () => request<SmeListItem[]>("/smes"),
  sme: (id: string) => request<SmeDetailOut>(`/smes/${id}`),

  search: (q: string) => request<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
};

export const CURRENT_WEEK = "2026-08-24";
