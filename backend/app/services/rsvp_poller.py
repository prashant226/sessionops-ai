"""Background RSVP polling (live mode only).

Google Calendar RSVP changes aren't pushed to us -- there's no webhook
subscription here, since that needs a publicly reachable HTTPS endpoint,
which localhost isn't. Instead, a lightweight asyncio loop (started from
main.py's lifespan) periodically calls the same polling logic the manual
"Re-check Availability" button uses, so RSVP responses and declines get
picked up without anyone having to click anything. Still not instant, but
closer to real-time than a fully manual check.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session as DbSession

from .. import models
from ..config import get_settings
from ..db import SessionLocal
from .calendar_adapter import read_rsvp_status
from .draft_engine import apply_rsvp_transition

logger = logging.getLogger("sessionops.rsvp_poller")

POLL_INTERVAL_SECONDS = 30

WATCHED_STATUSES = {
    models.AssignmentStatus.APPROVED.value,
    models.AssignmentStatus.REASSIGNED.value,
    models.AssignmentStatus.CONFIRMED.value,
}


def poll_all_pending_rsvps(db: DbSession, week_start: str | None = None) -> dict:
    """Checks every assignment (or just one week's, if given) with an
    outstanding or previously-accepted invite for an RSVP change, applying
    whatever's found via the shared apply_rsvp_transition logic. Returns a
    small summary; never raises -- a single bad event lookup shouldn't take
    down the whole poll."""
    query = db.query(models.Assignment).filter(models.Assignment.status.in_(WATCHED_STATUSES))
    if week_start:
        query = query.join(models.Session, models.Assignment.session_id == models.Session.session_id).filter(
            models.Session.week_start == week_start
        )
    rows = query.filter(models.Assignment.calendar_event_id.isnot(None)).all()
    updated = []
    for a in rows:
        try:
            sme = db.get(models.Sme, a.sme_id) if a.sme_id else None
            if not sme:
                continue
            rsvp = read_rsvp_status(db, a.calendar_event_id, sme.email)
            if rsvp and rsvp != a.rsvp_status and rsvp != "PENDING":
                apply_rsvp_transition(db, a, rsvp)
                updated.append(a.assignment_id)
        except Exception:
            logger.exception("RSVP poll failed for assignment %s", a.assignment_id)
    return {"checked": len(rows), "updated": updated}


async def rsvp_polling_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        if not settings.is_live:
            continue
        db = SessionLocal()
        try:
            result = poll_all_pending_rsvps(db)
            if result["updated"]:
                logger.info("RSVP poll: %d assignment(s) updated", len(result["updated"]))
        except Exception:
            logger.exception("RSVP polling loop iteration failed")
        finally:
            db.close()
