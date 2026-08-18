from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from .. import models, schemas
from ..config import get_settings
from ..db import get_db
from ..services import draft_engine
from ..services.activity_log import log
from ..services.calendar_adapter import create_event_and_invite, CalendarNotConnectedError
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


@router.get("/weeks", response_model=list[schemas.WeekSummary])
def list_weeks(db: DbSession = Depends(get_db)):
    rows = db.query(models.Session.week_start).distinct().all()
    return [schemas.WeekSummary(week_start=r[0], has_data=True) for r in rows]


@router.get("/sessions", response_model=list[schemas.AssignmentOut])
def list_sessions(week_start: str, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .order_by(models.Session.start_datetime)
        .all()
    )
    return [serialize_assignment(db, a, include_candidates=False) for a in rows]


@router.get("/assignments/{assignment_id}", response_model=schemas.AssignmentOut)
def get_assignment(assignment_id: str, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    return serialize_assignment(db, a)


@router.post("/generate")
def generate_draft(week_start: str, db: DbSession = Depends(get_db)):
    """Streams real progress events (newline-delimited JSON) as the engine
    actually completes each stage -- no artificial delays."""

    def event_stream():
        def emit(stage: str, detail: dict | None = None):
            yield json.dumps({"stage": stage, **(detail or {})}) + "\n"

        yield from emit("loading_sessions")
        sessions = draft_engine.sessions_needing_draft(db, week_start)
        yield from emit("loading_sessions_done", {"count": len(sessions)})

        yield from emit("checking_availability")
        yield from emit("applying_hard_constraints")
        yield from emit("evaluating_expertise")
        yield from emit("optimizing_workload_fairness")

        confirmed_count = pending_count = unfilled_count = 0
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
        result = create_event_and_invite(
            db, session.topic,
            f"{session.class_type} · {session.required_level} · scheduled via SessionOps AI",
            sme.email, session.start_datetime, session.duration_mins, session.timezone,
        )
    except CalendarNotConnectedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    a.calendar_event_id = result.calendar_event_id
    a.status = models.AssignmentStatus.APPROVED.value
    a.rsvp_status = models.RsvpStatus.PENDING.value
    db.commit()

    log(db, a.assignment_id, "Ops", f"Ops approved {sme.name}")
    log(db, a.assignment_id, "System", "Calendar invitation sent")
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/edit", response_model=schemas.AssignmentOut)
def edit_assignment(assignment_id: str, payload: schemas.EditRequest, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    session = a.session or db.get(models.Session, a.session_id)
    sme = db.get(models.Sme, payload.sme_id)
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found.")

    match = evaluate_candidates(db, session)
    candidate = next((c for c in match.candidates if c.sme_id == payload.sme_id), None)

    if candidate is None or not candidate.eligible:
        reason = candidate.elimination_reason if candidate else "Not eligible for this session."
        if not payload.override_hard_constraint:
            raise HTTPException(status_code=409, detail=f"This assignment conflicts with a hard constraint. {reason}")
        a.sme_id = sme.sme_id
        a.match_score = None
        a.status = models.AssignmentStatus.OVERRIDDEN.value
        a.reason = f"Manually overridden by Ops despite a hard constraint conflict: {reason}"
        a.flags = ["hard_override"]
        db.commit()
        log(db, a.assignment_id, "Ops", f"Ops overrode a hard constraint to assign {sme.name} ({reason})")
    else:
        a.sme_id = candidate.sme_id
        a.match_score = candidate.total_score
        a.status = models.AssignmentStatus.EDITED.value
        a.reason = f"Manually selected by Ops. {sme.name} scored {candidate.total_score}/100."
        a.flags = ["fairness_warning"] if any("workload" in w.lower() for w in candidate.warnings) else []
        db.commit()
        log(db, a.assignment_id, "Ops", f"Ops changed the assignment to {sme.name} ({candidate.total_score}/100)")

    from ..services.draft_engine import _snapshot
    a.candidates_snapshot = _snapshot(match)
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/assignments/{assignment_id}/reject", response_model=schemas.AssignmentOut)
def reject_recommendation(assignment_id: str, payload: schemas.RejectRequest, db: DbSession = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    session = a.session or db.get(models.Session, a.session_id)
    rejected_sme = db.get(models.Sme, a.sme_id) if a.sme_id else None

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
def sync_rsvp(week_start: str, db: DbSession = Depends(get_db)):
    """Live mode only: polls Google Calendar for every outstanding or
    previously-accepted invite in this week and applies any RSVP change
    found. A background loop (see services/rsvp_poller.py) also does this
    automatically every 30s while the server is running -- this endpoint is
    for an immediate manual check (the Re-check Availability button). In
    mock mode this is a no-op -- use the drawer's simulate control instead."""
    settings = get_settings()
    if not settings.is_live:
        return {"status": "skipped", "reason": "INTEGRATION_MODE is mock; use the RSVP simulate control instead.", "updated": []}
    result = poll_all_pending_rsvps(db, week_start=week_start)
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

    match = evaluate_candidates(db, session, exclude_sme_ids={a.original_sme_id} if a.original_sme_id else set())
    candidate = next((c for c in match.candidates if c.sme_id == payload.sme_id), None)
    if candidate is None or not candidate.eligible:
        reason = candidate.elimination_reason if candidate else "Not eligible for this session."
        if not payload.override_hard_constraint:
            raise HTTPException(status_code=409, detail=f"This assignment conflicts with a hard constraint. {reason}")

    try:
        result = create_event_and_invite(
            db, session.topic,
            f"{session.class_type} · {session.required_level} · replacement invite via SessionOps AI",
            sme.email, session.start_datetime, session.duration_mins, session.timezone,
        )
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
    log(db, a.assignment_id, "Ops", f"Replacement invitation sent to {sme.name}")
    db.commit()
    db.refresh(a)
    return serialize_assignment(db, a)


@router.post("/recheck-availability")
def recheck_availability(week_start: str, db: DbSession = Depends(get_db)):
    active_statuses = {
        models.AssignmentStatus.APPROVED.value, models.AssignmentStatus.CONFIRMED.value,
        models.AssignmentStatus.EDITED.value, models.AssignmentStatus.REASSIGNED.value,
        models.AssignmentStatus.OVERRIDDEN.value,
    }
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start, models.Assignment.status.in_(active_statuses))
        .all()
    )
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
    from datetime import timedelta
    db.add(models.CalendarBusyBlock(
        sme_id=a.sme_id, title="New external meeting",
        start_datetime=session.start_datetime, end_datetime=session.start_datetime + timedelta(minutes=session.duration_mins),
    ))
    db.commit()
    return {"status": "ok"}


@router.get("/final-review", response_model=schemas.FinalReviewOut)
def final_review(week_start: str, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .all()
    )
    confirmed = sum(1 for a in rows if a.status in (models.AssignmentStatus.CONFIRMED.value, models.AssignmentStatus.FINALIZED.value))
    edited = sum(1 for a in rows if a.status in (models.AssignmentStatus.EDITED.value, models.AssignmentStatus.OVERRIDDEN.value))
    pending = sum(1 for a in rows if a.status in (
        models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.APPROVED.value,
        models.AssignmentStatus.REASSIGNMENT_REQUIRED.value, models.AssignmentStatus.REASSIGNED.value,
    ))
    unfilled = sum(1 for a in rows if a.status == models.AssignmentStatus.UNFILLED.value)
    critical = sum(1 for a in rows if any(f in ("no_qualified_sme", "qualified_but_unavailable", "reassignment_required", "no_replacement_accepted", "new_conflict") for f in (a.flags or [])))
    warnings = sum(1 for a in rows if any(f in ("fairness_warning", "tentative_rsvp") for f in (a.flags or [])))

    meta = db.get(models.WeekMeta, week_start)
    return schemas.FinalReviewOut(
        week_start=week_start, total_sessions=len(rows), confirmed=confirmed, edited=edited,
        pending=pending, unfilled=unfilled, critical=critical, warnings=warnings,
        finalized=bool(meta and meta.finalized),
    )


@router.post("/finalize")
def finalize_week(week_start: str, payload: schemas.FinalizeRequest, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .all()
    )
    unresolved = [a for a in rows if a.status in (
        models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.REASSIGNMENT_REQUIRED.value,
        models.AssignmentStatus.UNFILLED.value,
    )]
    if unresolved and not payload.force:
        raise HTTPException(status_code=409, detail=f"This schedule contains {len(unresolved)} unresolved exception(s). Finalize with exception to proceed anyway.")

    for a in rows:
        if a.status != models.AssignmentStatus.UNFILLED.value:
            a.status = models.AssignmentStatus.FINALIZED.value
    from datetime import datetime, timezone
    meta = db.get(models.WeekMeta, week_start) or models.WeekMeta(week_start=week_start)
    meta.finalized = True
    meta.finalized_at = datetime.now(timezone.utc)
    db.add(meta)
    db.commit()
    return {"status": "finalized", "week_start": week_start, "sessions": len(rows)}
