"""Deterministic matching engine.

Everything in this module is pure, explainable business logic per the product
spec: hard constraint filtering, then soft scoring (expertise / performance /
fairness / preference), then deterministic tie-breaking. OpenAI is never the
authority here -- `services.semantic` only supplies human-readable phrasing
and a bounded nudge to the expertise sub-score (see semantic.py docstring).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DbSession

from .. import models
from .semantic import semantic_expertise_boost

LEVEL_ORDER = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 4}

WEIGHTS = {
    "expertise": 40,
    "performance": 25,
    "fairness": 25,
    "preference": 10,
}

ROLLING_WEEKS = 4
WORKING_HOURS_START = 6  # local hour, inclusive
WORKING_HOURS_END = 22  # local hour, exclusive


@dataclass
class CandidateResult:
    sme_id: str
    name: str
    eligible: bool
    elimination_reason: str | None
    total_score: float
    expertise: float
    performance: float
    fairness: float
    preference: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rolling_workload: int = 0
    team_average_workload: float = 0.0


@dataclass
class MatchResult:
    candidates: list[CandidateResult]
    qualified_count: int  # passed expertise + status, ignoring availability/capacity
    available_count: int  # also passed availability + capacity


def _session_window(session: models.Session) -> tuple[datetime, datetime]:
    start = session.start_datetime
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=session.duration_mins)
    return start, end


def _local_hour(dt_utc: datetime, tz_name: str) -> int:
    try:
        return dt_utc.astimezone(ZoneInfo(tz_name)).hour
    except Exception:
        return dt_utc.hour


def _rolling_workload(db: DbSession, sme_id: str, week_start: str, current_week_draft_counts: dict[str, int]) -> int:
    """Sum of assignment_history rows for the 4 weeks up to (and including) the
    scheduling week, plus assignments already made *this run* (dynamic
    recalculation per spec section 13)."""
    week_dt = datetime.strptime(week_start, "%Y-%m-%d")
    weeks = [(week_dt - timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(ROLLING_WEEKS)]
    rows = (
        db.query(models.AssignmentHistory)
        .filter(models.AssignmentHistory.sme_id == sme_id, models.AssignmentHistory.week_start.in_(weeks))
        .all()
    )
    historical = sum(r.sessions_assigned for r in rows if r.week_start != week_start)
    return historical + current_week_draft_counts.get(sme_id, 0)


def _team_average_workload(db: DbSession, sme_ids: list[str], week_start: str, current_week_draft_counts: dict) -> float:
    if not sme_ids:
        return 0.0
    total = sum(_rolling_workload(db, sid, week_start, current_week_draft_counts) for sid in sme_ids)
    return round(total / len(sme_ids), 1)


def _performance_for(db: DbSession, sme_id: str, topic: str, class_type: str) -> models.SmePerformance | None:
    exact = (
        db.query(models.SmePerformance)
        .filter(
            models.SmePerformance.sme_id == sme_id,
            models.SmePerformance.topic == topic,
            models.SmePerformance.class_type == class_type,
        )
        .first()
    )
    if exact:
        return exact
    return (
        db.query(models.SmePerformance)
        .filter(models.SmePerformance.sme_id == sme_id, models.SmePerformance.topic == topic)
        .first()
    )


def _has_calendar_conflict(db: DbSession, sme_id: str, start: datetime, end: datetime) -> bool:
    blocks = db.query(models.CalendarBusyBlock).filter(models.CalendarBusyBlock.sme_id == sme_id).all()
    for b in blocks:
        b_start, b_end = b.start_datetime, b.end_datetime
        if b_start.tzinfo is None:
            b_start = b_start.replace(tzinfo=timezone.utc)
        if b_end.tzinfo is None:
            b_end = b_end.replace(tzinfo=timezone.utc)
        if start < b_end and end > b_start:
            return True
    return False


def _has_assignment_overlap(
    db: DbSession, sme_id: str, session_id: str, start: datetime, end: datetime, active_statuses: set[str]
) -> bool:
    rows = (
        db.query(models.Assignment, models.Session)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Assignment.sme_id == sme_id, models.Assignment.session_id != session_id)
        .filter(models.Assignment.status.in_(active_statuses))
        .all()
    )
    for assignment, other_session in rows:
        o_start, o_end = _session_window(other_session)
        if start < o_end and end > o_start:
            return True
    return False


def _daily_count(
    db: DbSession, sme_id: str, session_id: str, day_key: str, active_statuses: set[str]
) -> int:
    rows = (
        db.query(models.Assignment, models.Session)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Assignment.sme_id == sme_id, models.Assignment.session_id != session_id)
        .filter(models.Assignment.status.in_(active_statuses))
        .all()
    )
    count = 0
    for assignment, other_session in rows:
        s, _ = _session_window(other_session)
        if s.date().isoformat() == day_key:
            count += 1
    return count


ACTIVE_ASSIGNMENT_STATUSES = {
    models.AssignmentStatus.PENDING_REVIEW.value,
    models.AssignmentStatus.APPROVED.value,
    models.AssignmentStatus.CONFIRMED.value,
    models.AssignmentStatus.EDITED_PENDING_APPROVAL.value,
    models.AssignmentStatus.EXCEPTION_PENDING_APPROVAL.value,
    models.AssignmentStatus.REASSIGNED.value,
    models.AssignmentStatus.FINALIZED.value,
}


def evaluate_candidates(
    db: DbSession,
    session: models.Session,
    exclude_sme_ids: set[str] | None = None,
) -> MatchResult:
    exclude_sme_ids = exclude_sme_ids or set()
    all_smes = db.query(models.Sme).all()
    start, end = _session_window(session)
    day_key = start.date().isoformat()

    # Current-run dynamic workload: count DRAFT/PENDING_REVIEW/APPROVED assignments
    # already produced in this generation pass so fairness recalculates live.
    draft_rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == session.week_start)
        .filter(models.Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES))
        .all()
    )
    current_week_draft_counts: dict[str, int] = {}
    for a in draft_rows:
        if a.sme_id:
            current_week_draft_counts[a.sme_id] = current_week_draft_counts.get(a.sme_id, 0) + 1

    active_sme_ids = [s.sme_id for s in all_smes if s.status == models.SmeStatus.ACTIVE.value]
    team_avg = _team_average_workload(db, active_sme_ids, session.week_start, current_week_draft_counts)

    required_level_rank = LEVEL_ORDER.get(session.required_level, 1)

    results: list[CandidateResult] = []
    qualified_count = 0
    available_count = 0

    for sme in all_smes:
        if sme.sme_id in exclude_sme_ids:
            continue

        reasons: list[str] = []
        warnings: list[str] = []

        if sme.status != models.SmeStatus.ACTIVE.value:
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, f"SME is {sme.status}", 0, 0, 0, 0, 0)
            )
            continue

        skills = {s.lower() for s in (sme.primary_skills or [])} | {s.lower() for s in (sme.secondary_skills or [])}
        primary = {s.lower() for s in (sme.primary_skills or [])}
        topic_key = session.topic.lower()
        has_expertise = any(topic_key == s or topic_key in s or s in topic_key for s in skills)
        level_ok = LEVEL_ORDER.get(sme.expertise_level, 0) >= required_level_rank

        if not has_expertise:
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, "Required expertise not available", 0, 0, 0, 0, 0)
            )
            continue
        if not level_ok:
            results.append(
                CandidateResult(
                    sme.sme_id,
                    sme.name,
                    False,
                    f"Required level {session.required_level} not met ({sme.expertise_level})",
                    0, 0, 0, 0, 0,
                )
            )
            continue

        qualified_count += 1

        if session.mode == "Offline" and session.location and sme.base_location != session.location:
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, f"Offline location mismatch ({sme.base_location})", 0, 0, 0, 0, 0)
            )
            continue

        local_hour = _local_hour(start, sme.timezone)
        if not (WORKING_HOURS_START <= local_hour < WORKING_HOURS_END):
            results.append(
                CandidateResult(
                    sme.sme_id, sme.name, False,
                    f"Session falls outside working hours in {sme.timezone} ({local_hour}:00 local)",
                    0, 0, 0, 0, 0,
                )
            )
            continue

        if _has_calendar_conflict(db, sme.sme_id, start, end):
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, "Calendar conflict at session time", 0, 0, 0, 0, 0)
            )
            continue

        if _has_assignment_overlap(db, sme.sme_id, session.session_id, start, end, ACTIVE_ASSIGNMENT_STATUSES):
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, "Overlaps an existing assignment", 0, 0, 0, 0, 0)
            )
            continue

        if _daily_count(db, sme.sme_id, session.session_id, day_key, ACTIVE_ASSIGNMENT_STATUSES) >= sme.max_sessions_per_day:
            results.append(
                CandidateResult(sme.sme_id, sme.name, False, f"Daily capacity ({sme.max_sessions_per_day}) exceeded", 0, 0, 0, 0, 0)
            )
            continue

        available_count += 1

        # ---- Soft scoring ----
        is_exact_primary_match = topic_key in primary
        expertise_score = 28 if is_exact_primary_match else 20
        if level_ok and LEVEL_ORDER.get(sme.expertise_level, 0) > required_level_rank:
            expertise_score += 4
        # The semantic nudge is only meaningful for a secondary-skill (less
        # certain) match -- an exact primary match already has full credit,
        # so skip it there. This also matters a lot for cost/latency in live
        # mode: it keeps real OpenAI calls down to a small fraction of
        # candidates instead of one per eligible candidate per session.
        if is_exact_primary_match:
            semantic_bonus, semantic_note = 0.0, None
        else:
            semantic_bonus, semantic_note = semantic_expertise_boost(session.topic, sme.primary_skills, sme.secondary_skills)
        expertise_score = min(WEIGHTS["expertise"], expertise_score + semantic_bonus)
        reasons.append(f"{session.topic} expertise" if topic_key in primary else f"Related expertise in {session.topic}")
        if semantic_note:
            reasons.append(semantic_note)

        perf = _performance_for(db, sme.sme_id, session.topic, session.class_type)
        if perf:
            perf_pct = (perf.avg_quality_score / 100 * 0.5) + (perf.avg_learner_rating / 5 * 0.3) + (perf.reliability_score / 100 * 0.2)
            performance_score = round(perf_pct * WEIGHTS["performance"], 1)
            reasons.append(f"Strong {session.class_type.lower()} performance ({perf.sessions_delivered} sessions, {perf.avg_learner_rating}/5)")
        else:
            performance_score = WEIGHTS["performance"] * 0.55
            warnings.append("No historical performance data for this topic/class type")

        workload = _rolling_workload(db, sme.sme_id, session.week_start, current_week_draft_counts)
        spread = max(1.0, team_avg if team_avg > 0 else 1.0)
        relative = (workload - team_avg) / spread
        fairness_score = max(0.0, min(WEIGHTS["fairness"], WEIGHTS["fairness"] * (1 - max(0.0, relative) * 0.6)))
        if workload <= team_avg:
            reasons.append("Fair 4-week workload")
        if team_avg > 0 and workload >= team_avg * 1.5 and workload - team_avg >= 3:
            warnings.append(f"{sme.name} is above rolling workload average ({workload} vs team average {team_avg})")

        pref = db.query(models.SmePreference).filter(models.SmePreference.sme_id == sme.sme_id).first()
        preference_score = 0.0
        if pref:
            if pref.preferred_topics and session.topic in pref.preferred_topics:
                preference_score += WEIGHTS["preference"] * 0.5
            if pref.preferred_class_types and session.class_type in pref.preferred_class_types:
                preference_score += WEIGHTS["preference"] * 0.3
            if pref.preferred_start_time and pref.preferred_end_time:
                pref_start_h = int(pref.preferred_start_time.split(":")[0])
                pref_end_h = int(pref.preferred_end_time.split(":")[0])
                if pref_start_h <= local_hour < pref_end_h:
                    preference_score += WEIGHTS["preference"] * 0.2
                else:
                    warnings.append(f"Outside {sme.name.split()[0]}'s preferred working hours ({pref.preferred_start_time}-{pref.preferred_end_time} local)")
        preference_score = round(min(WEIGHTS["preference"], preference_score), 1)
        if preference_score >= WEIGHTS["preference"] * 0.5:
            reasons.append("Preference fit")

        reasons.append("Available at session time")

        total = round(expertise_score + performance_score + fairness_score + preference_score, 1)

        results.append(
            CandidateResult(
                sme_id=sme.sme_id,
                name=sme.name,
                eligible=True,
                elimination_reason=None,
                total_score=total,
                expertise=round(expertise_score, 1),
                performance=round(performance_score, 1),
                fairness=round(fairness_score, 1),
                preference=preference_score,
                reasons=reasons,
                warnings=warnings,
                rolling_workload=workload,
                team_average_workload=team_avg,
            )
        )

    def sort_key(c: CandidateResult):
        last_assigned = (
            db.query(models.Assignment)
            .join(models.Session, models.Assignment.session_id == models.Session.session_id)
            .filter(models.Assignment.sme_id == c.sme_id)
            .filter(models.Assignment.status == models.AssignmentStatus.CONFIRMED.value)
            .order_by(models.Session.start_datetime.desc())
            .first()
        )
        recency = last_assigned.session.start_datetime if last_assigned else datetime.min.replace(tzinfo=timezone.utc)
        return (
            -c.total_score,
            c.rolling_workload,
            -c.performance,
            recency,
        )

    eligible = sorted([c for c in results if c.eligible], key=sort_key)
    ineligible = [c for c in results if not c.eligible]

    return MatchResult(candidates=eligible + ineligible, qualified_count=qualified_count, available_count=available_count)
