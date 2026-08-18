from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from .. import models, schemas
from ..config import get_settings
from ..db import get_db
from ..services import draft_engine, period
from ..services.activity_log import log
from ..services.calendar_adapter import (
    CalendarNotConnectedError,
    InviteAlreadySentError,
    create_event_and_invite,
    event_link,
    resend_invite,
)
from ..services.matching_engine import evaluate_candidates
from ..services.rsvp_poller import poll_all_pending_rsvps
from ..services.serialize import serialize_assignment

router = APIRouter(prefix="/schedule", tags=["schedule"])

MAX_REPLACEMENT_ATTEMPTS = 3


def _get_assignment(db: DbSession, assignment_id: str) -> models.Assignment:
    a = db.get(models.Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return a


@router.get("/period-status", response_model=schemas.PeriodStatusOut)
def period_status(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    return schemas.PeriodStatusOut(**period.get_period_status(db, start_date, end_date))


@router.post("/check-overlap", response_model=schemas.OverlapCheckOut)
def check_overlap(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    """Called before generating a draft for a new period, so the frontend
    can warn about an overlapping existing schedule instead of silently
    creating a confusing second draft over the same dates (product spec
    sections 5 and 28)."""
    conflict = period.find_overlapping_period(db, start_date, end_date)
    if not conflict:
        return schemas.OverlapCheckOut(overlap=None)
    count = period.assignments_in_range(db, conflict.start_date, conflict.end_date).count()
    return schemas.OverlapCheckOut(overlap=schemas.PeriodConflictOut(
        start_date=conflict.start_date, end_date=conflict.end_date, status=conflict.status, assignment_count=count,
    ))


@router.get("/sessions", response_model=list[schemas.AssignmentOut])
def list_sessions(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    rows = period.assignments_in_range(db, start_date, end_date).order_by(models.Session.start_datetime).all()
    return [serialize_assignment(db, a, include_candidates=False) for a in rows]


@router.post("/reset")
def reset_period(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    """Wipes every assignment (and its activity log) for the given date
    range back to a blank slate -- KPIs go to 0, the Review List goes
    empty, and Generate Draft has to be run again to repopulate it. Source
    data (Sessions, SMEs, performance, history, preferences, calendar busy
    blocks) is untouched -- this only clears the operational review state,
    not the underlying dataset. Does NOT delete any real Google Calendar
    events already created for approved assignments in live mode -- those
    stay on the calendar; only the app's own record of them is cleared."""
    rows = period.assignments_in_range(db, start_date, end_date).all()
    count = len(rows)
    for a in rows:
        db.query(models.AssignmentActivity).filter(models.AssignmentActivity.assignment_id == a.assignment_id).delete()
        db.delete(a)

    existing_period = (
        db.query(models.SchedulePeriod)
        .filter(models.SchedulePeriod.start_date == start_date, models.SchedulePeriod.end_date == end_date)
        .first()
    )
    if existing_period:
        db.delete(existing_period)

    db.commit()
    return {"status": "ok", "start_date": start_date, "end_date": end_date, "cleared": count}


@router.get("/assignments/{assignment_id}", response_model=schemas.AssignmentOut)
def get_assignment(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    return serialize_assignment(db, a)


@router.post("/generate")
def generate_draft(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    """Streams real progress events (newline-delimited JSON) as the engine
    actually completes each stage -- no artificial delays. Registers this
    range as a SchedulePeriod so it shows up in the Draft/Finalized header
    and participates in overlap detection for future periods."""

    def event_stream():
        def emit(stage: str, detail: dict | None = None):
            yield json.dumps({"stage": stage, **(detail or {})}) + "\n"

        yield from emit("loading_sessions")
        sessions = draft_engine.sessions_needing_draft(db, start_date, end_date)
        yield from emit("loading_sessions_done", {"count": len(sessions)})

        yield from emit("checking_availability")
        yield from emit("applying_hard_constraints")
        yield from emit("evaluating_expertise")
        yield from emit("optimizing_workload_fairness")

        pending_count = unfilled_count = 0
        for session in sessions:
            match = evaluate_candidates(db, session)
            assignment = db.query(models.Assignment).filter(models.Assignment.session_id == session.session_id).first()
            assignment = draft_engine.apply_draft_to_assignment(db, session, match, assignment)
            if assignment.status == models.AssignmentStatus.UNFILLED.value:
                unfilled_count += 1
            else:
                pending_count += 1
            yield from emit("session_processed", {
                "session_id": session.session_id, "topic": session.topic,
                "status": assignment.status, "sme_name": (db.get(models.Sme, assignment.sme_id).name if assignment.sme_id else None),
                "match_score": assignment.match_score,
            })

        yield from emit("detecting_conflicts")
        yield from emit("preparing_review_queue")

        period.get_or_create_period(db, start_date, end_date)

        yield from emit("done", {
            "sessions_processed": len(sessions), "pending_review": pending_count, "unfilled": unfilled_count,
        })

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/assignments/{assignment_id}/approve", response_model=schemas.AssignmentOut)
def approve_assignment(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if not a.sme_id:
        raise HTTPException(status_code=409, detail="No SME assigned to approve.")
    sme = db.get(models.Sme, a.sme_id)
    session = a.session or db.get(models.Session, a.session_id)

    try:
        result = create_event_and_invite(db, a, session, sme)
    except InviteAlreadySentError:
        raise HTTPException(status_code=409, detail="An invitation already exists for this assignment. Use Resend Invite or Open Event instead.")
    except CalendarNotConnectedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    a.calendar_event_id = result.calendar_event_id
    a.status = models.AssignmentStatus.APPROVED.value
    a.rsvp_status = models.RsvpStatus.PENDING.value
    # Refresh the display reason so it no longer reads "pending approval"
    # now that it's actually approved, and clear the now-resolved
    # exception_pending flag (a fairness_warning, if any, is still useful
    # context and stays).
    if a.sme_id != a.ai_recommended_sme_id and a.ai_recommended_sme_id:
        ai_sme = db.get(models.Sme, a.ai_recommended_sme_id)
        a.reason = (
            f"Ops selected {sme.name} over the AI recommendation "
            f"({ai_sme.name if ai_sme else 'unknown'} · {a.ai_recommended_score}). Approved and invited."
        )
    else:
        a.reason = f"{sme.name} approved and invited."
    a.flags = [f for f in (a.flags or []) if f != "exception_pending"]
    db.commit()

    from ..services.calendar_adapter import get_calendar_recipient
    log(db, a.assignment_id, "Ops", f"Ops approved {sme.name}")
    log(db, a.assignment_id, "System", f"Calendar invitation sent to {get_calendar_recipient(sme)}")
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/resend-invite", response_model=schemas.AssignmentOut)
def resend_assignment_invite(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if not a.calendar_event_id:
        raise HTTPException(status_code=409, detail="No invitation has been sent for this assignment yet.")
    sme = db.get(models.Sme, a.sme_id) if a.sme_id else None
    try:
        resend_invite(db, a.calendar_event_id, sme.email if sme else None)
    except CalendarNotConnectedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    log(db, a.assignment_id, "Ops", "Calendar invitation resent")
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.get("/assignments/{assignment_id}/event-link")
def get_event_link(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if not a.calendar_event_id:
        raise HTTPException(status_code=409, detail="No calendar event exists for this assignment.")
    return {"url": event_link(a.calendar_event_id)}


EXCEPTION_ELIGIBLE_MARKERS = ("daily capacity",)  # substring match against elimination_reason, case-insensitive


@router.post("/assignments/{assignment_id}/edit", response_model=schemas.AssignmentOut)
def edit_assignment(assignment_id: str, payload: schemas.EditRequest, db: DbSession = Depends(get_db)):
    """Editing an assignment is never itself an approval. A valid candidate
    lands in EDITED_PENDING_APPROVAL; a capacity-blocked one can become
    EXCEPTION_PENDING_APPROVAL if Ops gives a reason. Every other hard
    constraint (inactive, missing expertise, wrong level, calendar conflict,
    offline location mismatch, ...) has no override path at all -- this
    endpoint always 409s for those, and the assignment's stored state is
    left untouched so Ops just picks someone else."""
    a = _get_assignment(db, assignment_id)
    if a.status in (models.AssignmentStatus.APPROVED.value, models.AssignmentStatus.CONFIRMED.value,
                    models.AssignmentStatus.REASSIGNED.value, models.AssignmentStatus.FINALIZED.value):
        raise HTTPException(
            status_code=409,
            detail="blocked::This assignment is already approved with an active Calendar invite. Report SME Dropout to change the assignee instead.",
        )
    session = a.session or db.get(models.Session, a.session_id)
    sme = db.get(models.Sme, payload.sme_id)
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found.")

    match = evaluate_candidates(db, session)
    candidate = next((c for c in match.candidates if c.sme_id == payload.sme_id), None)
    from ..services.draft_engine import _snapshot

    if candidate is None or not candidate.eligible:
        reason = candidate.elimination_reason if candidate else "Not eligible for this session."
        exception_eligible = any(marker in reason.lower() for marker in EXCEPTION_ELIGIBLE_MARKERS)

        if not exception_eligible:
            raise HTTPException(status_code=409, detail=f"blocked::{reason}")

        if not (payload.exception_reason and payload.exception_reason.strip()):
            raise HTTPException(status_code=409, detail=f"exception_reason_required::{reason}")

        a.sme_id = sme.sme_id
        a.match_score = None
        a.status = models.AssignmentStatus.EXCEPTION_PENDING_APPROVAL.value
        a.exception_reason = payload.exception_reason.strip()
        a.reason = f"Ops requested an exception to assign {sme.name} despite: {reason}"
        a.flags = ["exception_pending"]
        a.candidates_snapshot = _snapshot(match)
        db.commit()
        log(db, a.assignment_id, "Ops", f"Ops requested an exception for {sme.name} ({reason}): {payload.exception_reason.strip()}")
    else:
        a.sme_id = candidate.sme_id
        a.match_score = candidate.total_score
        a.status = models.AssignmentStatus.EDITED_PENDING_APPROVAL.value
        a.exception_reason = None
        a.reason = f"Ops selected {sme.name}, pending approval. {sme.name} scored {candidate.total_score}/100."
        a.flags = ["fairness_warning"] if any("workload" in w.lower() for w in candidate.warnings) else []
        a.candidates_snapshot = _snapshot(match)
        db.commit()
        log(db, a.assignment_id, "Ops", f"Ops selected {sme.name} ({candidate.total_score}/100) -- pending approval")

    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/revert", response_model=schemas.AssignmentOut)
def revert_assignment(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if not a.ai_recommended_sme_id:
        raise HTTPException(status_code=409, detail="No AI recommendation on record for this assignment.")
    return serialize_assignment(db, draft_engine.revert_to_ai_recommendation(db, a))


@router.post("/assignments/{assignment_id}/reject", response_model=schemas.AssignmentOut)
def reject_recommendation(assignment_id: str, payload: schemas.RejectRequest, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    session = a.session or db.get(models.Session, a.session_id)

    log(db, a.assignment_id, "Ops", f"Ops rejected the recommendation ({payload.reason})")

    exclude = {a.sme_id} if a.sme_id else set()
    match = evaluate_candidates(db, session, exclude_sme_ids=exclude)
    a = draft_engine.apply_draft_to_assignment(db, session, match, a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/rsvp/simulate", response_model=schemas.AssignmentOut)
def simulate_rsvp(assignment_id: str, payload: schemas.RsvpSimulateRequest, db: DbSession = Depends(get_db)):
    """Demo-only control standing in for a real Calendar RSVP webhook/poll.
    See services/calendar_adapter.py and POST /sync-rsvp for the live-mode
    equivalent."""
    a = _get_assignment(db, assignment_id)
    if payload.rsvp not in ("ACCEPTED", "TENTATIVE", "DECLINED"):
        raise HTTPException(status_code=400, detail="Invalid RSVP value.")
    if not a.sme_id:
        raise HTTPException(status_code=409, detail="No SME currently invited on this assignment.")
    return serialize_assignment(db, draft_engine.apply_rsvp_transition(db, a, payload.rsvp))


@router.post("/sync-rsvp")
def sync_rsvp(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    """Live mode only: polls Google Calendar for every outstanding or
    previously-accepted invite in this date range and applies any RSVP
    change found. A background loop (see services/rsvp_poller.py) also does
    this automatically every ~60s while the server is running -- this
    endpoint is for an immediate manual check (the Re-check Availability
    button). In mock mode this is a no-op -- use the drawer's simulate
    control instead."""
    settings = get_settings()
    if not settings.is_live:
        return {"status": "skipped", "reason": "INTEGRATION_MODE is mock; use the RSVP simulate control instead.", "updated": []}
    result = poll_all_pending_rsvps(db, start_date=start_date, end_date=end_date)
    return {"status": "ok", **result}


@router.post("/assignments/{assignment_id}/dropout", response_model=schemas.AssignmentOut)
def report_dropout(assignment_id: str, payload: schemas.DropoutRequest, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if not a.sme_id:
        raise HTTPException(status_code=409, detail="No SME currently assigned to report a dropout for.")
    sme = db.get(models.Sme, a.sme_id)
    note = f" ({payload.note})" if payload.note else ""
    a.rsvp_status = models.RsvpStatus.DECLINED.value
    log(db, a.assignment_id, "Ops", f"Ops reported a dropout for {sme.name}{note}")
    db.commit()
    draft_engine.run_reassignment(db, a, sme.sme_id)
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/replacement/send", response_model=schemas.AssignmentOut)
def send_replacement_invite(assignment_id: str, payload: schemas.EditRequest, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    session = a.session or db.get(models.Session, a.session_id)
    sme = db.get(models.Sme, payload.sme_id)
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found.")
    if a.replacement_attempt_count >= MAX_REPLACEMENT_ATTEMPTS:
        raise HTTPException(status_code=409, detail=f"Maximum of {MAX_REPLACEMENT_ATTEMPTS} replacement invitation attempts already reached for this session.")

    match = evaluate_candidates(db, session, exclude_sme_ids={a.original_sme_id} if a.original_sme_id else set())
    candidate = next((c for c in match.candidates if c.sme_id == payload.sme_id), None)
    if candidate is None or not candidate.eligible:
        reason = candidate.elimination_reason if candidate else "Not eligible for this session."
        raise HTTPException(status_code=409, detail=f"blocked::{reason}")

    # A replacement is a fresh invite for a (now different) SME -- clear the
    # prior event id first so create_event_and_invite's idempotency check
    # doesn't mistake this for a duplicate of the original invite.
    a.calendar_event_id = None
    try:
        result = create_event_and_invite(db, a, session, sme)
    except CalendarNotConnectedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    a.sme_id = sme.sme_id
    a.match_score = candidate.total_score if candidate else None
    a.status = models.AssignmentStatus.REASSIGNED.value
    a.rsvp_status = models.RsvpStatus.PENDING.value
    a.calendar_event_id = result.calendar_event_id
    a.replacement_attempt_count = (a.replacement_attempt_count or 0) + 1
    a.flags = []
    from ..services.draft_engine import _snapshot
    a.candidates_snapshot = _snapshot(match)
    db.commit()
    from ..services.calendar_adapter import get_calendar_recipient
    log(db, a.assignment_id, "Ops", f"Replacement invitation sent to {sme.name} ({get_calendar_recipient(sme)})")
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/recheck-availability")
def recheck_availability(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    # Only assignments that have actually been approved (real invite sent /
    # commitment made) are worth re-checking -- an EDITED/EXCEPTION pending
    # approval hasn't been committed to yet.
    active_statuses = {
        models.AssignmentStatus.APPROVED.value, models.AssignmentStatus.CONFIRMED.value,
        models.AssignmentStatus.REASSIGNED.value,
    }
    rows = period.assignments_in_range(db, start_date, end_date).filter(models.Assignment.status.in_(active_statuses)).all()
    new_conflicts = []
    for a in rows:
        if not a.sme_id:
            continue
        session = a.session or db.get(models.Session, a.session_id)
        match = evaluate_candidates(db, session)
        candidate = next((c for c in match.candidates if c.sme_id == a.sme_id), None)
        if candidate is None or not candidate.eligible:
            a.flags = list(set((a.flags or []) + ["new_conflict"]))
            db.commit()
            reason = candidate.elimination_reason if candidate else "No longer eligible."
            log(db, a.assignment_id, "System", f"Re-check availability found a new conflict: {reason}")
            db.commit()
            new_conflicts.append(a.assignment_id)
    return {"checked": len(rows), "new_conflicts": new_conflicts}


@router.post("/assignments/{assignment_id}/simulate-new-conflict")
def simulate_new_conflict(assignment_id: str, db: DbSession = Depends(get_db)):
    """Demo/testing aid only: fabricates a newly-created busy block for the
    currently assigned SME at the session time, so 'Re-check Availability'
    has something real to discover (spec scenario 12). Not a normal Ops
    action -- surfaced only in Settings > Demo Tools."""
    a = _get_assignment(db, assignment_id)
    if not a.sme_id:
        raise HTTPException(status_code=409, detail="No SME assigned to simulate a conflict for.")
    session = a.session or db.get(models.Session, a.session_id)
    db.add(models.CalendarBusyBlock(
        sme_id=a.sme_id, title="New external meeting",
        start_datetime=session.start_datetime, end_datetime=session.start_datetime + timedelta(minutes=session.duration_mins),
    ))
    db.commit()
    return {"status": "ok"}


@router.get("/final-review", response_model=schemas.FinalReviewOut)
def final_review(start_date: str, end_date: str, db: DbSession = Depends(get_db)):
    rows = period.assignments_in_range(db, start_date, end_date).all()
    confirmed = sum(1 for a in rows if a.status in (models.AssignmentStatus.CONFIRMED.value, models.AssignmentStatus.FINALIZED.value))
    # "Edited" here means still sitting unapproved after an Ops edit/
    # exception request -- once approved it's indistinguishable in status
    # from a non-edited approval (see insights.py's activity-based override
    # tracking for the all-time rate instead).
    edited = sum(1 for a in rows if a.status in (
        models.AssignmentStatus.EDITED_PENDING_APPROVAL.value, models.AssignmentStatus.EXCEPTION_PENDING_APPROVAL.value,
    ))
    pending = sum(1 for a in rows if a.status in (
        models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.APPROVED.value,
        models.AssignmentStatus.REASSIGNMENT_REQUIRED.value, models.AssignmentStatus.REASSIGNED.value,
    ))
    unfilled = sum(1 for a in rows if a.status == models.AssignmentStatus.UNFILLED.value)
    critical = sum(1 for a in rows if any(f in ("no_qualified_sme", "qualified_but_unavailable", "reassignment_required", "no_replacement_accepted", "new_conflict") for f in (a.flags or [])))
    warnings = sum(1 for a in rows if any(f in ("fairness_warning", "tentative_rsvp") for f in (a.flags or [])))

    existing_period = (
        db.query(models.SchedulePeriod)
        .filter(models.SchedulePeriod.start_date == start_date, models.SchedulePeriod.end_date == end_date)
        .first()
    )
    return schemas.FinalReviewOut(
        start_date=start_date, end_date=end_date, total_sessions=len(rows), confirmed=confirmed, edited=edited,
        pending=pending, unfilled=unfilled, critical=critical, warnings=warnings,
        finalized=bool(existing_period and existing_period.status == "FINALIZED"),
    )


@router.post("/finalize")
def finalize_period(start_date: str, end_date: str, payload: schemas.FinalizeRequest, db: DbSession = Depends(get_db)):
    rows = period.assignments_in_range(db, start_date, end_date).all()
    unresolved = [a for a in rows if a.status in (
        models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.REASSIGNMENT_REQUIRED.value,
        models.AssignmentStatus.UNFILLED.value, models.AssignmentStatus.EDITED_PENDING_APPROVAL.value,
        models.AssignmentStatus.EXCEPTION_PENDING_APPROVAL.value,
    )]
    if unresolved and not payload.force:
        raise HTTPException(status_code=409, detail=f"This schedule contains {len(unresolved)} unresolved exception(s). Finalize with exception to proceed anyway.")

    for a in rows:
        if a.status != models.AssignmentStatus.UNFILLED.value:
            a.status = models.AssignmentStatus.FINALIZED.value

    sp = period.get_or_create_period(db, start_date, end_date)
    sp.status = "FINALIZED"
    sp.finalized_at = datetime.now(timezone.utc)
    db.add(sp)
    db.commit()
    return {"status": "finalized", "start_date": start_date, "end_date": end_date, "sessions": len(rows)}
