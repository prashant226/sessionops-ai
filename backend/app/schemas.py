from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    ops_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    ops_name: str


class SmeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sme_id: str
    name: str
    primary_skills: list[str]
    secondary_skills: list[str]
    expertise_level: str
    timezone: str
    base_location: str
    status: str
    max_sessions_per_day: int
    email: Optional[str] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: str
    topic: str
    class_type: str
    required_level: str
    start_datetime: datetime
    duration_mins: int
    timezone: str
    mode: str
    location: Optional[str] = None
    week_start: str


class ScoreBreakdown(BaseModel):
    expertise: float
    expertise_max: float = 40
    performance: float
    performance_max: float = 25
    fairness: float
    fairness_max: float = 25
    preference: float
    preference_max: float = 10


class CandidateOut(BaseModel):
    sme_id: str
    name: str
    total_score: float
    breakdown: ScoreBreakdown
    reasons: list[str]
    warnings: list[str] = []
    eligible: bool
    rolling_workload: int
    team_average_workload: float


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: datetime
    actor: str
    message: str


class AssignmentOut(BaseModel):
    assignment_id: str
    session: SessionOut
    sme_id: Optional[str] = None
    sme_name: Optional[str] = None
    match_score: Optional[float] = None
    status: str
    rsvp_status: str
    reason: Optional[str] = None
    flags: list[str] = []
    original_sme_id: Optional[str] = None
    replacement_attempt_count: int = 0
    calendar_event_id: Optional[str] = None
    calendar_recipient_email: Optional[str] = None
    ai_recommended_sme_id: Optional[str] = None
    ai_recommended_sme_name: Optional[str] = None
    ai_recommended_score: Optional[float] = None
    exception_reason: Optional[str] = None
    breakdown: Optional[ScoreBreakdown] = None
    candidates: list[CandidateOut] = []
    activity: list[ActivityOut] = []
    exception_type: Optional[str] = None
    exception_severity: Optional[str] = None
    exception_detail: Optional[dict] = None


class ApproveRequest(BaseModel):
    pass


class EditRequest(BaseModel):
    sme_id: str
    # Only used for the narrow exception-eligible constraint set (currently:
    # daily capacity exceeded). A required, non-empty reason is what turns a
    # blocked capacity pick into an EXCEPTION_PENDING_APPROVAL request --
    # hard constraints outside that set (inactive, missing expertise, wrong
    # level, calendar conflict, offline location) have no override path at
    # all, regardless of this field.
    exception_reason: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str


class RsvpSimulateRequest(BaseModel):
    rsvp: str  # ACCEPTED | TENTATIVE | DECLINED


class DropoutRequest(BaseModel):
    note: Optional[str] = None


class KpiOut(BaseModel):
    total_sessions: int
    confirmed: int
    pending_review: int
    need_attention: int
    unfilled: int


class FinalReviewOut(BaseModel):
    start_date: str
    end_date: str
    total_sessions: int
    confirmed: int
    edited: int
    pending: int
    unfilled: int
    critical: int
    warnings: int
    finalized: bool


class FinalizeRequest(BaseModel):
    force: bool = False


class PeriodStatusOut(BaseModel):
    status: str  # NONE | DRAFT | FINALIZED
    assignment_count: int


class PeriodConflictOut(BaseModel):
    start_date: str
    end_date: str
    status: str
    assignment_count: int


class OverlapCheckOut(BaseModel):
    overlap: Optional[PeriodConflictOut] = None


class DemoConfigOut(BaseModel):
    demo_mode: bool
    demo_calendar_email: Optional[str] = None


class NeedsAttentionItem(BaseModel):
    session_id: str
    topic: str
    class_type: str
    severity: str
    headline: str
    detail: str
    starts_in: Optional[str] = None
