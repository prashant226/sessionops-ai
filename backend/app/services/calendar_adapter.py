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
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from . import google_auth

GOOGLE_TO_RSVP = {
    "needsAction": "PENDING",
    "accepted": "ACCEPTED",
    "tentative": "TENTATIVE",
    "declined": "DECLINED",
}

CALENDAR_ID = "primary"


class CalendarNotConnectedError(RuntimeError):
    pass


@dataclass
class CalendarEventResult:
    calendar_event_id: str
    rsvp_status: str  # PENDING to start


def create_event_and_invite(
    db: DbSession,
    session_topic: str,
    session_description: str,
    sme_email: str | None,
    start: datetime,
    duration_mins: int,
    timezone_name: str,
) -> CalendarEventResult:
    settings = get_settings()
    if settings.is_live:
        return _live_create_event(db, session_topic, session_description, sme_email, start, duration_mins, timezone_name)
    return CalendarEventResult(calendar_event_id=f"evt_{uuid.uuid4().hex[:10]}", rsvp_status="PENDING")


def _service(db: DbSession):
    from googleapiclient.discovery import build

    creds = google_auth.get_credentials(db)
    if creds is None:
        raise CalendarNotConnectedError("Google Calendar is not connected. Connect it from Settings first.")
    return build("calendar", "v3", credentials=creds)


def _live_create_event(
    db: DbSession,
    session_topic: str,
    session_description: str,
    sme_email: str | None,
    start: datetime,
    duration_mins: int,
    timezone_name: str,
) -> CalendarEventResult:
    service = _service(db)
    end = start + timedelta(minutes=duration_mins)

    settings = get_settings()
    attendee_email = sme_email
    description = session_description
    if settings.google_test_attendee_email:
        description = f"{session_description}\n\n(Test mode: invite redirected from {sme_email or 'unknown'} to {settings.google_test_attendee_email}.)"
        attendee_email = settings.google_test_attendee_email

    body = {
        "summary": session_topic,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
        "attendees": [{"email": attendee_email}] if attendee_email else [],
        "reminders": {"useDefault": True},
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=body, sendUpdates="all").execute()
    return CalendarEventResult(calendar_event_id=created["id"], rsvp_status="PENDING")


def read_rsvp_status(db: DbSession, calendar_event_id: str, sme_email: str | None) -> str | None:
    """Polls the event and maps the invited SME's attendee responseStatus via
    GOOGLE_TO_RSVP. Returns None in mock mode (RSVP there is driven by the
    demo simulate control instead) or if the event/attendee can't be read."""
    settings = get_settings()
    if not settings.is_live:
        return None
    try:
        service = _service(db)
        # If invites are being redirected to a test inbox (see
        # GOOGLE_TEST_ATTENDEE_EMAIL), that's who actually appears as the
        # attendee on the event -- match against that instead of the SME's
        # own (never-actually-invited) email.
        lookup_email = settings.google_test_attendee_email or sme_email
        event = service.events().get(calendarId=CALENDAR_ID, eventId=calendar_event_id).execute()
        for attendee in event.get("attendees", []):
            if lookup_email and attendee.get("email", "").lower() == lookup_email.lower():
                return GOOGLE_TO_RSVP.get(attendee.get("responseStatus"), "PENDING")
        return None
    except Exception:
        return None
