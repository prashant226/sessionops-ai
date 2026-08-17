from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from .. import models, schemas
from ..db import get_db
from ..services.serialize import serialize_assignment

router = APIRouter(prefix="/exceptions", tags=["exceptions"])

FILTER_FLAG_MAP = {
    "Availability": {"qualified_but_unavailable", "new_conflict"},
    "Expertise": {"no_qualified_sme", "hard_override"},
    "Fairness": {"fairness_warning"},
    "RSVP": {"tentative_rsvp", "reassignment_required"},
    "Unfilled": {"no_replacement_accepted"},
}

SEVERITY_RANK = {"Critical": 0, "Warning": 1}
URGENCY_ORDER = [
    "no_replacement_accepted", "no_qualified_sme", "qualified_but_unavailable",
    "reassignment_required", "new_conflict", "fairness_warning", "tentative_rsvp",
]


@router.get("", response_model=list[schemas.AssignmentOut])
def list_exceptions(week_start: str, filter: str = "All", db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .all()
    )

    def has_exception(a: models.Assignment) -> bool:
        flags = set(a.flags or [])
        return bool(flags) or a.status == models.AssignmentStatus.REASSIGNMENT_REQUIRED.value

    exceptional = [a for a in rows if has_exception(a)]

    if filter != "All":
        wanted = FILTER_FLAG_MAP.get(filter, set())
        if filter == "Critical":
            exceptional = [a for a in exceptional if any(f in {"no_qualified_sme", "qualified_but_unavailable", "reassignment_required", "no_replacement_accepted", "new_conflict"} for f in (a.flags or [])) or a.status == models.AssignmentStatus.REASSIGNMENT_REQUIRED.value]
        else:
            exceptional = [a for a in exceptional if set(a.flags or []) & wanted]

    def urgency_key(a: models.Assignment):
        flags = a.flags or []
        best = min((URGENCY_ORDER.index(f) for f in flags if f in URGENCY_ORDER), default=len(URGENCY_ORDER))
        session = a.session or db.get(models.Session, a.session_id)
        return (best, session.start_datetime)

    exceptional.sort(key=urgency_key)
    return [serialize_assignment(db, a, include_candidates=False) for a in exceptional]
