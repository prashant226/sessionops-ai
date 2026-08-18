import type {
  AssignmentOut,
  DemoConfigOut,
  FinalReviewOut,
  GenerateEvent,
  InsightsOut,
  KpiOut,
  NeedsAttentionItem,
  OverlapCheckOut,
  PeriodStatusOut,
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

function rangeQS(start_date: string, end_date: string) {
  return `start_date=${start_date}&end_date=${end_date}`;
}

export const api = {
  login: (ops_id: string, password: string) =>
    request<{ token: string; ops_name: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ ops_id, password }),
    }),

  sync: () => request<{ status: string; smes: number; sessions: number }>("/sync", { method: "POST" }),

  demoConfig: () => request<DemoConfigOut>("/config/demo"),

  kpis: (start_date: string, end_date: string) => request<KpiOut>(`/overview/kpis?${rangeQS(start_date, end_date)}`),
  needsAttention: (start_date: string, end_date: string) =>
    request<NeedsAttentionItem[]>(`/overview/needs-attention?${rangeQS(start_date, end_date)}`),

  listSessions: (start_date: string, end_date: string) =>
    request<AssignmentOut[]>(`/schedule/sessions?${rangeQS(start_date, end_date)}`),
  resetPeriod: (start_date: string, end_date: string) =>
    request<{ status: string; cleared: number }>(`/schedule/reset?${rangeQS(start_date, end_date)}`, { method: "POST" }),
  getAssignment: (id: string) => request<AssignmentOut>(`/schedule/assignments/${id}`),

  periodStatus: (start_date: string, end_date: string) =>
    request<PeriodStatusOut>(`/schedule/period-status?${rangeQS(start_date, end_date)}`),
  checkOverlap: (start_date: string, end_date: string) =>
    request<OverlapCheckOut>(`/schedule/check-overlap?${rangeQS(start_date, end_date)}`, { method: "POST" }),

  async generateDraft(start_date: string, end_date: string, onEvent: (e: GenerateEvent) => void): Promise<void> {
    const res = await fetch(`${BASE_URL}/schedule/generate?${rangeQS(start_date, end_date)}`, { method: "POST" });
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
  resendInvite: (assignmentId: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/resend-invite`, { method: "POST" }),
  eventLink: (assignmentId: string) => request<{ url: string }>(`/schedule/assignments/${assignmentId}/event-link`),
  edit: (assignmentId: string, sme_id: string, exception_reason?: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/edit`, {
      method: "POST",
      body: JSON.stringify({ sme_id, exception_reason }),
    }),
  revert: (assignmentId: string) => request<AssignmentOut>(`/schedule/assignments/${assignmentId}/revert`, { method: "POST" }),
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
  sendReplacement: (assignmentId: string, sme_id: string) =>
    request<AssignmentOut>(`/schedule/assignments/${assignmentId}/replacement/send`, {
      method: "POST",
      body: JSON.stringify({ sme_id }),
    }),
  recheckAvailability: (start_date: string, end_date: string) =>
    request<{ checked: number; new_conflicts: string[] }>(`/schedule/recheck-availability?${rangeQS(start_date, end_date)}`, {
      method: "POST",
    }),
  simulateNewConflict: (assignmentId: string) =>
    request<{ status: string }>(`/schedule/assignments/${assignmentId}/simulate-new-conflict`, { method: "POST" }),

  finalReview: (start_date: string, end_date: string) =>
    request<FinalReviewOut>(`/schedule/final-review?${rangeQS(start_date, end_date)}`),
  finalize: (start_date: string, end_date: string, force: boolean) =>
    request<{ status: string }>(`/schedule/finalize?${rangeQS(start_date, end_date)}`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),

  exceptions: (start_date: string, end_date: string, filter = "All") =>
    request<AssignmentOut[]>(`/exceptions?${rangeQS(start_date, end_date)}&filter=${encodeURIComponent(filter)}`),

  insights: (start_date: string, end_date: string) => request<InsightsOut>(`/insights?${rangeQS(start_date, end_date)}`),

  smes: () => request<SmeListItem[]>("/smes"),
  sme: (id: string) => request<SmeDetailOut>(`/smes/${id}`),

  search: (q: string) => request<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),

  googleStatus: () => request<{ connected: boolean; account_email: string | null }>("/auth/google/status"),
  googleLogin: () => request<{ auth_url: string }>("/auth/google/login"),
  googleDisconnect: () => request<{ status: string }>("/auth/google/disconnect", { method: "POST" }),
  syncRsvp: (start_date: string, end_date: string) =>
    request<{ status: string; checked: number; updated: string[] }>(`/schedule/sync-rsvp?${rangeQS(start_date, end_date)}`, {
      method: "POST",
    }),
};

export const DEFAULT_PERIOD_START = "2026-08-24";
export const DEFAULT_PERIOD_END = "2026-08-30";
