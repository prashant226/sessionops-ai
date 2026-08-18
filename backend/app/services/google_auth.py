"""Google OAuth connection management.

One Ops-team Google account is connected (the "organizer"). Calendar events
are created on that account's calendar with SMEs added as attendees -- SMEs
receive a normal Calendar invite by email and RSVP through Google directly;
they never need their own OAuth connection. This matches the product spec's
Phase 1 spike: OAuth -> connect calendar -> create event -> add attendee ->
send invite -> read attendee responseStatus.
"""

from __future__ import annotations

from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session as DbSession

from .. import models
from ..config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

TOKEN_ROW_ID = "default"


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def build_auth_url(state: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = get_settings().google_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # force a refresh_token every time, useful in dev
    )
    return auth_url


def exchange_code(code: str, state: str) -> Credentials:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = get_settings().google_redirect_uri
    flow.fetch_token(code=code)
    return flow.credentials


def save_credentials(db: DbSession, creds: Credentials) -> models.GoogleAuthToken:
    email = None
    try:
        oauth2 = build("oauth2", "v2", credentials=creds)
        email = oauth2.userinfo().get().execute().get("email")
    except Exception:
        pass

    row = db.get(models.GoogleAuthToken, TOKEN_ROW_ID)
    if row is None:
        row = models.GoogleAuthToken(id=TOKEN_ROW_ID)
        db.add(row)

    row.account_email = email
    row.access_token = creds.token
    row.refresh_token = creds.refresh_token or row.refresh_token  # Google omits this on re-consent sometimes
    row.token_uri = creds.token_uri
    row.scopes = list(creds.scopes or SCOPES)
    row.expiry = creds.expiry
    row.connected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def get_credentials(db: DbSession) -> Credentials | None:
    row = db.get(models.GoogleAuthToken, TOKEN_ROW_ID)
    if row is None or not row.refresh_token:
        return None
    settings = get_settings()
    creds = Credentials(
        token=row.access_token,
        refresh_token=row.refresh_token,
        token_uri=row.token_uri or "https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=row.scopes or SCOPES,
    )
    if not creds.valid:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
        row.access_token = creds.token
        row.expiry = creds.expiry
        db.commit()
    return creds


def connection_status(db: DbSession) -> dict:
    row = db.get(models.GoogleAuthToken, TOKEN_ROW_ID)
    if row is None or not row.refresh_token:
        return {"connected": False, "account_email": None}
    return {"connected": True, "account_email": row.account_email, "connected_at": row.connected_at}


def disconnect(db: DbSession) -> None:
    row = db.get(models.GoogleAuthToken, TOKEN_ROW_ID)
    if row:
        db.delete(row)
        db.commit()
