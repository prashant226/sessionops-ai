export interface SessionOut {
  session_id: string;
  topic: string;
  class_type: string;
  required_level: string;
  start_datetime: string;
  duration_mins: number;
  timezone: string;
  mode: string;
  location: string | null;
  week_start: string;
}

export interface ScoreBreakdown {
  expertise: number;
  expertise_max: number;
  performance: number;
  performance_max: number;
  fairness: number;
  fairness_max: number;
  preference: number;
  preference_max: number;
}

export interface CandidateOut {
  sme_id: string;
  name: string;
  total_score: number;
  breakdown: ScoreBreakdown;
  reasons: string[];
  warnings: string[];
  eligible: boolean;
  rolling_workload: number;
  team_average_workload: number;
}

export interface ActivityOut {
  timestamp: string;
  actor: "AI" | "Ops" | "System" | string;
  message: string;
}

export type AssignmentStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "CONFIRMED"
  | "EDITED"
  | "OVERRIDDEN"
  | "REASSIGNMENT_REQUIRED"
  | "REASSIGNED"
  | "UNFILLED"
  | "FINALIZED";

export type RsvpStatus = "NONE" | "PENDING" | "ACCEPTED" | "TENTATIVE" | "DECLINED";

export interface AssignmentOut {
  assignment_id: string;
  session: SessionOut;
  sme_id: string | null;
  sme_name: string | null;
  match_score: number | null;
  status: AssignmentStatus;
  rsvp_status: RsvpStatus;
  reason: string | null;
  flags: string[];
  original_sme_id: string | null;
  replacement_attempt_count: number;
  calendar_event_id: string | null;
  calendar_recipient_email: string | null;
  breakdown: ScoreBreakdown | null;
  candidates: CandidateOut[];
  activity: ActivityOut[];
  exception_type: string | null;
  exception_severity: "Critical" | "Warning" | null;
  exception_detail: Record<string, unknown> | null;
}

export interface KpiOut {
  total_sessions: number;
  confirmed: number;
  pending_review: number;
  need_attention: number;
  unfilled: number;
}

export interface NeedsAttentionItem {
  session_id: string;
  topic: string;
  class_type: string;
  severity: "Critical" | "Warning" | "Info";
  headline: string;
  detail: string;
  starts_in: string | null;
}

export interface FinalReviewOut {
  start_date: string;
  end_date: string;
  total_sessions: number;
  confirmed: number;
  edited: number;
  pending: number;
  unfilled: number;
  critical: number;
  warnings: number;
  finalized: boolean;
}

export interface PeriodStatusOut {
  status: "NONE" | "DRAFT" | "FINALIZED";
  assignment_count: number;
}

export interface PeriodConflictOut {
  start_date: string;
  end_date: string;
  status: "DRAFT" | "FINALIZED";
  assignment_count: number;
}

export interface OverlapCheckOut {
  overlap: PeriodConflictOut | null;
}

export interface DemoConfigOut {
  demo_mode: boolean;
  demo_calendar_email: string | null;
}

export interface Metric {
  key: string;
  label: string;
  value: number | null;
  unit: "percent" | "minutes" | "count";
  definition: string;
  calculation: string;
  why_it_matters: string;
}

export interface WorkloadPoint {
  sme_id: string;
  name: string;
  rolling_workload: number;
}

export interface InsightsOut {
  efficiency: Metric[];
  ai_quality: Metric[];
  scheduling_quality: Metric[];
  workload: WorkloadPoint[];
  team_average_workload: number;
}

export interface SmeListItem {
  sme_id: string;
  name: string;
  status: string;
  timezone: string;
  base_location: string;
  expertise_level: string;
  primary_skills: string[];
  rolling_workload: number;
}

export interface PerformanceRow {
  topic: string;
  class_type: string;
  sessions_delivered: number;
  avg_learner_rating: number;
  avg_quality_score: number;
  reliability_score: number;
}

export interface SmeDetailOut {
  sme_id: string;
  name: string;
  email: string | null;
  calendar_recipient_email: string | null;
  status: string;
  timezone: string;
  base_location: string;
  primary_skills: string[];
  secondary_skills: string[];
  expertise_level: string;
  max_sessions_per_day: number;
  rolling_workload: number;
  performance: PerformanceRow[];
  preferences: {
    preferred_topics: string[];
    preferred_class_types: string[];
    preferred_start_time: string | null;
    preferred_end_time: string | null;
  } | null;
}

export interface SearchResult {
  type: "session" | "sme";
  id: string;
  label: string;
  sublabel: string;
}

export interface GenerateEvent {
  stage: string;
  session_id?: string;
  topic?: string;
  status?: string;
  sme_name?: string | null;
  match_score?: number | null;
  count?: number;
  sessions_processed?: number;
  pending_review?: number;
  unfilled?: number;
}
