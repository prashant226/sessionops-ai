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

from .. import models
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


class InviteAlreadySentError(RuntimeError):
    def __init__(self, calendar_event_id: str):
        self.calendar_event_id = calendar_event_id
        super().__init__("An invitation already exists for this assignment.")


@dataclass
class CalendarEventResult:
    calendar_event_id: str
    rsvp_status: str  # PENDING to start


def get_calendar_recipient(sme: models.Sme) -> str | None:
    """The single source of truth for "who actually gets the Calendar
    invite" (product spec section 41). In demo mode every invite is
    redirected to one real inbox, since the synthetic dataset's SME emails
    aren't real addresses. Never hardcoded here -- both values come from
    env (see config.py)."""
    settings = get_settings()
    if settings.demo_mode and settings.demo_calendar_email:
        return settings.demo_calendar_email
    return sme.email if sme else None


def build_event_content(session: models.Session) -> tuple[str, str]:
    title = f"[Learning] {session.topic} | {session.class_type}"
    description = (
        f"Session ID: {session.session_id}\n\n"
        f"Topic: {session.topic}\n"
        f"Class Type: {session.class_type}\n"
        f"Required Level: {session.required_level}\n\n"
        f"Please RSVP to confirm your availability."
    )
    return title, description


def create_event_and_invite(
    db: DbSession,
    assignment: models.Assignment,
    session: models.Session,
    sme: models.Sme,
) -> CalendarEventResult:
    """Idempotent: if this assignment already has a calendar_event_id, this
    raises InviteAlreadySentError instead of silently creating a duplicate
    event -- callers should offer Open Event / Resend Invite instead
    (product spec sections 43-44)."""
    if assignment.calendar_event_id:
        raise InviteAlreadySentError(assignment.calendar_event_id)

    settings = get_settings()
    recipient = get_calendar_recipient(sme)
    title, description = build_event_content(session)
    if settings.demo_mode and settings.demo_calendar_email and recipient != sme.email:
        description += f"\n\n(Demo mode: invite redirected from {sme.email or 'unknown'} to {recipient}.)"

    if settings.is_live:
        return _live_create_event(db, title, description, recipient, session.start_datetime, session.duration_mins, session.timezone)
    return CalendarEventResult(calendar_event_id=f"evt_{uuid.uuid4().hex[:10]}", rsvp_status="PENDING")


def resend_invite(db: DbSession, calendar_event_id: str, sme_email: str | None) -> None:
    """Re-sends the existing event's invitation without creating a new
    event -- Google re-notifies attendees when an event is patched with
    sendUpdates='all', even with no substantive change."""
    settings = get_settings()
    if not settings.is_live:
        return
    service = _service(db)
    service.events().patch(calendarId=CALENDAR_ID, eventId=calendar_event_id, body={}, sendUpdates="all").execute()


def event_link(calendar_event_id: str) -> str:
    return f"https://calendar.google.com/calendar/event?eid={calendar_event_id}"


def _service(db: DbSession):
    from googleapiclient.discovery import build

    creds = google_auth.get_credentials(db)
    if creds is None:
        raise CalendarNotConnectedError("Google Calendar is not connected. Connect it from Settings first.")
    return build("calendar", "v3", credentials=creds)


def _live_create_event(
    db: DbSession,
    title: str,
    description: str,
    attendee_email: str | None,
    start: datetime,
    duration_mins: int,
    timezone_name: str,
) -> CalendarEventResult:
    service = _service(db)
    end = start + timedelta(minutes=duration_mins)
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
        "attendees": [{"email": attendee_email}] if attendee_email else [],
        "reminders": {"useDefault": True},
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=body, sendUpdates="all").execute()
    return CalendarEventResult(calendar_event_id=created["id"], rsvp_status="PENDING")


def read_rsvp_status(db: DbSession, calendar_event_id: str, sme: models.Sme | None) -> str | None:
    """Polls the event and maps the invited attendee's responseStatus via
    GOOGLE_TO_RSVP. Returns None in mock mode (RSVP there is driven by the
    demo simulate control instead) or if the event/attendee can't be read."""
    settings = get_settings()
    if not settings.is_live:
        return None
    try:
        service = _service(db)
        lookup_email = get_calendar_recipient(sme) if sme else None
        event = service.events().get(calendarId=CALENDAR_ID, eventId=calendar_event_id).execute()
        for attendee in event.get("attendees", []):
            if lookup_email and attendee.get("email", "").lower() == lookup_email.lower():
                return GOOGLE_TO_RSVP.get(attendee.get("responseStatus"), "PENDING")
        return None
    except Exception:
        return None
