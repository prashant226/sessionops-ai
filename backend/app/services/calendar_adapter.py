"""Google Calendar adapter.

Mock mode fabricates a calendar_event_id and starts every invite in
PENDING/needsAction, matching the real Google response shape. RSVP
transitions are then driven either by the demo "simulate RSVP" control (mock
mode only) or, in live mode, by actually polling attendee responseStatus.
The rest of the app (RSVP processing, reassignment) is identical either way
because both adapters return the same three-state vocabulary: accepted,
tentative, declined.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..config import get_settings

GOOGLE_TO_RSVP = {
    "needsAction": "PENDING",
    "accepted": "ACCEPTED",
    "tentative": "TENTATIVE",
    "declined": "DECLINED",
}


@dataclass
class CalendarEventResult:
    calendar_event_id: str
    rsvp_status: str  # PENDING to start


def create_event_and_invite(session_topic: str, sme_email: str | None, start, end) -> CalendarEventResult:
    settings = get_settings()
    if settings.is_live and settings.google_client_id:
        return _live_create_event(session_topic, sme_email, start, end)
    return CalendarEventResult(calendar_event_id=f"evt_{uuid.uuid4().hex[:10]}", rsvp_status="PENDING")


def _live_create_event(session_topic: str, sme_email: str | None, start, end) -> CalendarEventResult:
    """Placeholder for the real Google Calendar API v3 events.insert call with
    sendUpdates="all" and a single attendee. See the Phase 1 spike checklist
    in the product spec: OAuth -> connect calendar -> create event -> add
    attendee -> send invite -> read attendee responseStatus."""
    raise NotImplementedError("Live Google Calendar integration not yet configured")


def read_rsvp_status(calendar_event_id: str) -> str | None:
    """In live mode, polls events.get and maps attendee responseStatus via
    GOOGLE_TO_RSVP. In mock mode RSVP changes are driven by the demo control
    (see routers/calendar.py simulate endpoint) so this is a no-op."""
    settings = get_settings()
    if settings.is_live and settings.google_client_id:
        raise NotImplementedError("Live Google Calendar integration not yet configured")
    return None
