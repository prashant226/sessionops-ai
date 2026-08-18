from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from .. import models
from .activity_log import log
from .matching_engine import MatchResult, evaluate_candidates
from .semantic import explain_recommendation
from .serialize import candidate_result_to_dict

MAX_REPLACEMENT_ATTEMPTS = 3
SNAPSHOT_SIZE = 6


def _snapshot(match: MatchResult) -> list[dict]:
    return [candidate_result_to_dict(c) for c in match.candidates[:SNAPSHOT_SIZE] if True]


def apply_draft_to_assignment(db: DbSession, session: models.Session, match: MatchResult, assignment: models.Assignment | None) -> models.Assignment:
    snapshot = _snapshot(match)
    top = match.candidates[0] if match.candidates and match.candidates[0].eligible else None

    if assignment is None:
        assignment = models.Assignment(session_id=session.session_id)
        db.add(assignment)
        db.flush()

    assignment.candidates_snapshot = snapshot
    assignment.qualified_count = match.qualified_count
    assignment.available_count = match.available_count

    if top:
        assignment.sme_id = top.sme_id
        assignment.match_score = top.total_score
        assignment.ai_recommended_sme_id = top.sme_id
        assignment.ai_recommended_score = top.total_score
        assignment.status = models.AssignmentStatus.PENDING_REVIEW.value
        assignment.reason = explain_recommendation(session.topic, session.class_type, top.name, top.reasons)
        flags = []
        for w in top.warnings:
            if "workload" in w.lower():
                flags.append("fairness_warning")
        assignment.flags = flags
        log(db, assignment.assignment_id, "AI", f"AI recommended {top.name} ({top.total_score}/100)")
    else:
        assignment.sme_id = None
        assignment.match_score = None
        assignment.status = models.AssignmentStatus.UNFILLED.value
        if match.qualified_count == 0:
            assignment.reason = f"No SME in the pool qualifies for {session.required_level} {session.topic}."
            assignment.flags = ["no_qualified_sme"]
            log(db, assignment.assignment_id, "AI", f"No qualified SME found for {session.required_level} {session.topic}")
        else:
            assignment.reason = f"{match.qualified_count} qualified SME(s) found, none available at this time."
            assignment.flags = ["qualified_but_unavailable"]
            log(db, assignment.assignment_id, "AI", f"{match.qualified_count} qualified SME(s) found, 0 available at this time")

    db.commit()
    db.refresh(assignment)
    return assignment


def generate_draft_for_session(db: DbSession, session: models.Session) -> models.Assignment:
    existing = db.query(models.Assignment).filter(models.Assignment.session_id == session.session_id).first()
    match = evaluate_candidates(db, session)
    return apply_draft_to_assignment(db, session, match, existing)


def sessions_needing_draft(db: DbSession, start_date: str, end_date: str) -> list[models.Session]:
    from .period import range_bounds

    start_dt, end_dt = range_bounds(start_date, end_date)
    sessions = (
        db.query(models.Session)
        .filter(models.Session.start_datetime >= start_dt, models.Session.start_datetime < end_dt)
        .order_by(models.Session.start_datetime)
        .all()
    )
    existing_ids = {
        row[0]
        for row in db.query(models.Assignment.session_id)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.start_datetime >= start_dt, models.Session.start_datetime < end_dt)
        .all()
    }
    return [s for s in sessions if s.session_id not in existing_ids]


def revert_to_ai_recommendation(db: DbSession, assignment: models.Assignment) -> models.Assignment:
    """Undoes an Ops edit/exception that hasn't been approved yet, restoring
    the assignment to the AI's own recommendation and back to
    PENDING_REVIEW. Only meaningful before approval -- once an invite has
    gone out this isn't offered in the UI."""
    if not assignment.ai_recommended_sme_id:
        raise ValueError("No AI recommendation on record for this assignment.")
    sme = db.get(models.Sme, assignment.ai_recommended_sme_id)
    assignment.sme_id = assignment.ai_recommended_sme_id
    assignment.match_score = assignment.ai_recommended_score
    assignment.status = models.AssignmentStatus.PENDING_REVIEW.value
    assignment.exception_reason = None
    assignment.flags = [f for f in (assignment.flags or []) if f not in ("fairness_warning", "exception_pending")]
    db.commit()
    log(db, assignment.assignment_id, "Ops", f"Ops reverted to the AI recommendation ({sme.name if sme else assignment.ai_recommended_sme_id})")
    db.commit()
    db.refresh(assignment)
    return assignment


def apply_rsvp_transition(db: DbSession, assignment: models.Assignment, rsvp: str) -> models.Assignment:
    """Shared RSVP business logic used by both the demo simulate control and
    real Google Calendar RSVP polling (see routers/schedule.py and
    services/calendar_adapter.py) -- one source of truth for what an
    accepted/tentative/declined response does to an assignment."""
    sme = db.get(models.Sme, assignment.sme_id)

    if rsvp == "ACCEPTED":
        assignment.rsvp_status = models.RsvpStatus.ACCEPTED.value
        assignment.status = models.AssignmentStatus.CONFIRMED.value
        assignment.flags = [f for f in (assignment.flags or []) if f != "tentative_rsvp"]
        db.commit()
        log(db, assignment.assignment_id, "System", f"{sme.name} accepted the invitation")
    elif rsvp == "TENTATIVE":
        assignment.rsvp_status = models.RsvpStatus.TENTATIVE.value
        assignment.flags = list(set((assignment.flags or []) + ["tentative_rsvp"]))
        db.commit()
        log(db, assignment.assignment_id, "System", f"{sme.name} responded Tentative")
    elif rsvp == "DECLINED":
        assignment.rsvp_status = models.RsvpStatus.DECLINED.value
        db.commit()
        log(db, assignment.assignment_id, "System", f"{sme.name} declined the invitation")
        if assignment.replacement_attempt_count >= MAX_REPLACEMENT_ATTEMPTS:
            assignment.status = models.AssignmentStatus.UNFILLED.value
            assignment.flags = ["no_replacement_accepted"]
            assignment.sme_id = None
            assignment.reason = f"{MAX_REPLACEMENT_ATTEMPTS} replacement invitation(s) sent, none accepted. No qualified SME remains available."
            db.commit()
            log(db, assignment.assignment_id, "System", "Maximum replacement attempts reached. No replacement accepted.")
        else:
            run_reassignment(db, assignment, sme.sme_id)

    db.refresh(assignment)
    return assignment


def run_reassignment(db: DbSession, assignment: models.Assignment, declining_sme_id: str) -> models.Assignment:
    """Called when an SME declines or Ops reports a dropout. Clears the SME,
    marks the assignment for reassignment, and re-runs matching (excluding
    the declining SME plus any prior failed replacement attempts) so Ops has
    a ranked recommendation ready to act on. Never auto-sends the invite."""
    session = assignment.session or db.get(models.Session, assignment.session_id)
    declining_sme = db.get(models.Sme, declining_sme_id)
    assignment.original_sme_id = assignment.original_sme_id or declining_sme_id
    assignment.sme_id = None
    assignment.status = models.AssignmentStatus.REASSIGNMENT_REQUIRED.value
    assignment.flags = ["reassignment_required"]
    assignment.reason = f"{declining_sme.name if declining_sme else 'The invited SME'} declined the calendar invitation. Reassignment required."

    exclude = {declining_sme_id}
    if assignment.original_sme_id:
        exclude.add(assignment.original_sme_id)
    match = evaluate_candidates(db, session, exclude_sme_ids=exclude)
    assignment.candidates_snapshot = _snapshot(match)
    assignment.qualified_count = match.qualified_count
    assignment.available_count = match.available_count
    db.commit()
    log(db, assignment.assignment_id, "AI", "Reassignment required. Re-running candidate matching.")
    db.commit()
    db.refresh(assignment)
    return assignment
