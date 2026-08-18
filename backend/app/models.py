import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SmeStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ON_LEAVE = "On Leave"


class AssignmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    CONFIRMED = "CONFIRMED"
    EDITED = "EDITED"
    OVERRIDDEN = "OVERRIDDEN"
    REASSIGNMENT_REQUIRED = "REASSIGNMENT_REQUIRED"
    REASSIGNED = "REASSIGNED"
    UNFILLED = "UNFILLED"
    FINALIZED = "FINALIZED"


class RsvpStatus(str, enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    TENTATIVE = "TENTATIVE"
    DECLINED = "DECLINED"


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    topic: Mapped[str] = mapped_column(String)
    class_type: Mapped[str] = mapped_column(String)
    required_level: Mapped[str] = mapped_column(String)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_mins: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="Online")
    location: Mapped[str] = mapped_column(String, nullable=True)
    week_start: Mapped[str] = mapped_column(String, index=True)

    assignments: Mapped[list["Assignment"]] = relationship(back_populates="session")


class Sme(Base):
    __tablename__ = "smes"

    sme_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    primary_skills: Mapped[list] = mapped_column(JSON, default=list)
    secondary_skills: Mapped[list] = mapped_column(JSON, default=list)
    expertise_level: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String)
    base_location: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=SmeStatus.ACTIVE.value)
    max_sessions_per_day: Mapped[int] = mapped_column(Integer, default=2)
    email: Mapped[str] = mapped_column(String, nullable=True)


class SmePerformance(Base):
    __tablename__ = "sme_performance"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    sme_id: Mapped[str] = mapped_column(String, ForeignKey("smes.sme_id"), index=True)
    topic: Mapped[str] = mapped_column(String)
    class_type: Mapped[str] = mapped_column(String)
    sessions_delivered: Mapped[int] = mapped_column(Integer, default=0)
    avg_learner_rating: Mapped[float] = mapped_column(Float, default=0)
    avg_quality_score: Mapped[float] = mapped_column(Float, default=0)
    reliability_score: Mapped[float] = mapped_column(Float, default=0)


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    sme_id: Mapped[str] = mapped_column(String, ForeignKey("smes.sme_id"), index=True)
    week_start: Mapped[str] = mapped_column(String, index=True)
    sessions_assigned: Mapped[int] = mapped_column(Integer, default=0)


class SmePreference(Base):
    __tablename__ = "sme_preferences"

    sme_id: Mapped[str] = mapped_column(String, ForeignKey("smes.sme_id"), primary_key=True)
    preferred_topics: Mapped[list] = mapped_column(JSON, default=list)
    preferred_class_types: Mapped[list] = mapped_column(JSON, default=list)
    preferred_start_time: Mapped[str] = mapped_column(String, nullable=True)
    preferred_end_time: Mapped[str] = mapped_column(String, nullable=True)


class CalendarBusyBlock(Base):
    """Synthetic busy periods for mock mode. In live mode this is superseded by
    real Google Calendar freebusy reads (see services/calendar_adapter.py)."""

    __tablename__ = "calendar_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    sme_id: Mapped[str] = mapped_column(String, ForeignKey("smes.sme_id"), index=True)
    title: Mapped[str] = mapped_column(String, default="Busy")
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.session_id"), index=True)
    sme_id: Mapped[str] = mapped_column(String, ForeignKey("smes.sme_id"), nullable=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default=AssignmentStatus.DRAFT.value)
    rsvp_status: Mapped[str] = mapped_column(String, default=RsvpStatus.NONE.value)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    original_sme_id: Mapped[str] = mapped_column(String, nullable=True)
    replacement_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    calendar_event_id: Mapped[str] = mapped_column(String, nullable=True)
    candidates_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    qualified_count: Mapped[int] = mapped_column(Integer, nullable=True)
    available_count: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    session: Mapped["Session"] = relationship(back_populates="assignments")
    activity: Mapped[list["AssignmentActivity"]] = relationship(
        back_populates="assignment", order_by="AssignmentActivity.timestamp"
    )


class GoogleAuthToken(Base):
    """Single-row table holding the Ops team's connected Google account
    (OAuth token). The organizer's calendar is used to create events and
    invite SMEs as attendees -- SMEs themselves never need their own OAuth
    connection, they just receive and respond to a normal Calendar invite."""

    __tablename__ = "google_auth_token"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    account_email: Mapped[str] = mapped_column(String, nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    token_uri: Mapped[str] = mapped_column(String, nullable=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class SchedulePeriod(Base):
    """An Ops-selected scheduling date range (arbitrary start/end, not
    assumed to be a calendar week). Created/updated whenever a draft is
    generated for a range; used to show the Draft/Finalized state header and
    to detect overlapping ranges before generating another schedule.
    Deliberately independent of Session.week_start, which is a fixed
    data-intrinsic tag used only for rolling fairness history -- selecting a
    different period here never changes what "week" a session's workload
    history is computed against."""

    __tablename__ = "schedule_periods"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    start_date: Mapped[str] = mapped_column(String, index=True)
    end_date: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="DRAFT")  # DRAFT | FINALIZED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class AssignmentActivity(Base):
    __tablename__ = "assignment_activity"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    assignment_id: Mapped[str] = mapped_column(String, ForeignKey("assignments.assignment_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actor: Mapped[str] = mapped_column(String)  # "AI" | "Ops" | "System"
    message: Mapped[str] = mapped_column(String)

    assignment: Mapped["Assignment"] = relationship(back_populates="activity")
