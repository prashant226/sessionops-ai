from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..services import google_auth

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

FRONTEND_SETTINGS_URL = "http://localhost:3000/settings"

# In-memory CSRF state store. Fine for a single-operator local prototype;
# a multi-instance deployment would persist this (e.g. a short-lived DB row
# or signed cookie) instead.
_pending_states: set[str] = set()


@router.get("/login")
def login():
    state = secrets.token_urlsafe(24)
    _pending_states.add(state)
    auth_url = google_auth.build_auth_url(state)
    return {"auth_url": auth_url}


@router.get("/callback")
def callback(code: str = Query(...), state: str = Query(...), db: DbSession = Depends(get_db)):
    if state not in _pending_states:
        return RedirectResponse(f"{FRONTEND_SETTINGS_URL}?google_error=invalid_state")
    _pending_states.discard(state)

    try:
        creds = google_auth.exchange_code(code, state)
        google_auth.save_credentials(db, creds)
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_SETTINGS_URL}?google_error={type(e).__name__}")

    return RedirectResponse(f"{FRONTEND_SETTINGS_URL}?google_connected=1")


@router.get("/status")
def status(db: DbSession = Depends(get_db)):
    return google_auth.connection_status(db)


@router.post("/disconnect")
def disconnect(db: DbSession = Depends(get_db)):
    google_auth.disconnect(db)
    return {"status": "disconnected"}
