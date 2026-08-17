from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/overview", tags=["overview"])

CRITICAL_FLAGS = {"no_qualified_sme", "qualified_but_unavailable", "reassignment_required", "no_replacement_accepted", "new_conflict"}
WARNING_FLAGS = {"fairness_warning", "tentative_rsvp"}


def _starts_in(session: models.Session) -> str:
    now = datetime.now(timezone.utc)
    start = session.start_datetime
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    delta = start - now
    hours = delta.total_seconds() / 3600
    if hours < 0:
        return "started"
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)}m"
    if hours < 48:
        return f"{int(hours)}h"
    return f"{int(hours / 24)}d"


@router.get("/kpis", response_model=schemas.KpiOut)
def kpis(week_start: str, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .all()
    )
    total = len(rows)
    confirmed = sum(1 for a in rows if a.status in (models.AssignmentStatus.CONFIRMED.value, models.AssignmentStatus.FINALIZED.value))
    pending = sum(1 for a in rows if a.status in (models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.APPROVED.value))
    unfilled = sum(1 for a in rows if a.status == models.AssignmentStatus.UNFILLED.value)
    need_attention = sum(1 for a in rows if any(f in CRITICAL_FLAGS | WARNING_FLAGS for f in (a.flags or [])) or a.status == models.AssignmentStatus.REASSIGNMENT_REQUIRED.value)
    return schemas.KpiOut(total_sessions=total, confirmed=confirmed, pending_review=pending, need_attention=need_attention, unfilled=unfilled)


@router.get("/needs-attention", response_model=list[schemas.NeedsAttentionItem])
def needs_attention(week_start: str, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .order_by(models.Session.start_datetime)
        .all()
    )
    items: list[schemas.NeedsAttentionItem] = []
    for a in rows:
        flags = a.flags or []
        session = a.session or db.get(models.Session, a.session_id)
        if "no_qualified_sme" in flags:
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Critical", headline="No qualified SME available",
                detail=f"No SME meets {session.required_level} {session.topic}.", starts_in=_starts_in(session)))
        elif "qualified_but_unavailable" in flags:
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Critical", headline="Qualified SMEs exist, none available",
                detail="All qualified SMEs have a calendar conflict at this time.", starts_in=_starts_in(session)))
        elif "no_replacement_accepted" in flags:
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Critical", headline="No replacement accepted",
                detail=f"{a.replacement_attempt_count} replacement invitation(s) sent, none accepted.", starts_in=_starts_in(session)))
        elif a.status == models.AssignmentStatus.REASSIGNMENT_REQUIRED.value:
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Critical", headline="Reassignment required",
                detail="The invited SME declined. A replacement recommendation is ready for review.", starts_in=_starts_in(session)))
        elif "fairness_warning" in flags:
            sme = db.get(models.Sme, a.sme_id) if a.sme_id else None
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Warning", headline=f"{sme.name if sme else 'SME'} is above rolling workload average",
                detail="Assigning this session further increases workload imbalance.", starts_in=_starts_in(session)))
        elif "tentative_rsvp" in flags:
            sme = db.get(models.Sme, a.sme_id) if a.sme_id else None
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Warning", headline="SME RSVP pending",
                detail=f"{sme.name if sme else 'SME'} has not fully committed to this session.", starts_in=_starts_in(session)))
        elif a.status == models.AssignmentStatus.APPROVED.value and a.rsvp_status == models.RsvpStatus.PENDING.value:
            items.append(schemas.NeedsAttentionItem(
                session_id=session.session_id, topic=session.topic, class_type=session.class_type,
                severity="Info", headline="SME RSVP pending", detail="Calendar invitation sent, awaiting response.",
                starts_in=_starts_in(session)))

    severity_rank = {"Critical": 0, "Warning": 1, "Info": 2}
    items.sort(key=lambda i: severity_rank.get(i.severity, 3))
    return items
