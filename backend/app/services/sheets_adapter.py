"""Google Sheets ingestion adapter.

Mock mode re-seeds the local database from the bundled synthetic fixtures
(services/seed.py). Live mode reads the same six tabs (Sessions,
SME_Profiles, SME_Performance, Assignment_History, SME_Preferences,
Calendar_Events) from a real Google Sheet via the Sheets API and upserts the
same tables through the same seed_source_data path, so the rest of the app
never has to know which source it came from.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from .. import models
from ..config import get_settings
from . import google_auth
from .seed import seed_all

TABS = ["Sessions", "SME_Profiles", "SME_Performance", "Assignment_History", "SME_Preferences", "Calendar_Events"]


def sync_from_sheets(db: DbSession) -> dict:
    settings = get_settings()
    if settings.is_live and settings.google_sheets_spreadsheet_id:
        return _live_sync(db)
    counts = seed_all(db, reset=True)
    return {"source": "mock_fixtures", **counts}


def _rows_to_dicts(values: list[list[str]]) -> list[dict]:
    if not values:
        return []
    header, *rows = values
    out = []
    for row in rows:
        row = row + [""] * (len(header) - len(row))  # pad short rows
        out.append(dict(zip(header, row)))
    return out


def _split_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [s.strip() for s in raw.replace(";", ",").split(",") if s.strip()]


def _parse_dt(raw: str) -> datetime:
    """Google Sheets returns date/time cells in its own display format by
    default (e.g. '2026-08-24 4:30:00' -- space-separated, not zero-padded),
    not strict ISO 8601, so datetime.fromisoformat() alone isn't enough.
    dateutil.parser handles that plus the ISO format our own CSVs use."""
    from dateutil import parser as dtparser

    raw = raw.strip()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return dtparser.parse(raw)


def _live_sync(db: DbSession) -> dict:
    from googleapiclient.discovery import build

    settings = get_settings()
    creds = google_auth.get_credentials(db)
    if creds is None:
        raise RuntimeError("Google is not connected. Connect it from Settings first.")

    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    data = {}
    for tab in TABS:
        result = sheet.values().get(spreadsheetId=settings.google_sheets_spreadsheet_id, range=tab).execute()
        data[tab] = _rows_to_dicts(result.get("values", []))

    for row in data["SME_Profiles"]:
        _upsert_sme(db, row)
    db.flush()

    for row in data["Sessions"]:
        _upsert_session(db, row)

    db.query(models.SmePerformance).delete()
    for row in data["SME_Performance"]:
        db.add(models.SmePerformance(
            sme_id=row["sme_id"], topic=row["topic"], class_type=row["class_type"],
            sessions_delivered=int(row.get("sessions_delivered") or 0),
            avg_learner_rating=float(row.get("avg_learner_rating") or 0),
            avg_quality_score=float(row.get("avg_quality_score") or 0),
            reliability_score=float(row.get("reliability_score") or 0),
        ))

    db.query(models.AssignmentHistory).delete()
    for row in data["Assignment_History"]:
        db.add(models.AssignmentHistory(
            sme_id=row["sme_id"], week_start=row["week_start"],
            sessions_assigned=int(row.get("sessions_assigned") or 0),
        ))

    db.query(models.SmePreference).delete()
    for row in data["SME_Preferences"]:
        db.add(models.SmePreference(
            sme_id=row["sme_id"],
            preferred_topics=_split_list(row.get("preferred_topics", "")),
            preferred_class_types=_split_list(row.get("preferred_class_types", "")),
            preferred_start_time=row.get("preferred_start_time") or None,
            preferred_end_time=row.get("preferred_end_time") or None,
        ))

    import uuid

    db.query(models.CalendarBusyBlock).delete()
    for row in data["Calendar_Events"]:
        db.add(models.CalendarBusyBlock(
            event_id=row.get("event_id") or f"evt_{uuid.uuid4().hex[:10]}",
            sme_id=row["sme_id"], title=row.get("title") or "Busy",
            start_datetime=_parse_dt(row["start_datetime"]), end_datetime=_parse_dt(row["end_datetime"]),
        ))

    db.commit()
    return {
        "source": "google_sheets", "smes": len(data["SME_Profiles"]), "sessions": len(data["Sessions"]),
        "performance_rows": len(data["SME_Performance"]), "history_rows": len(data["Assignment_History"]),
        "preferences": len(data["SME_Preferences"]), "busy_blocks": len(data["Calendar_Events"]),
    }


def _upsert_sme(db: DbSession, row: dict) -> None:
    sme = db.get(models.Sme, row["sme_id"])
    if sme is None:
        sme = models.Sme(sme_id=row["sme_id"])
        db.add(sme)
    sme.name = row.get("name", sme.sme_id)
    sme.primary_skills = _split_list(row.get("primary_skills", ""))
    sme.secondary_skills = _split_list(row.get("secondary_skills", ""))
    sme.expertise_level = row.get("expertise_level", "Intermediate")
    sme.timezone = row.get("timezone", "UTC")
    sme.base_location = row.get("base_location", "")
    sme.status = row.get("status", "Active")
    sme.max_sessions_per_day = int(row.get("max_sessions_per_day") or 2)
    sme.email = row.get("email") or None


def _upsert_session(db: DbSession, row: dict) -> None:
    session = db.get(models.Session, row["session_id"])
    if session is None:
        session = models.Session(session_id=row["session_id"])
        db.add(session)
    session.topic = row.get("topic", "")
    session.class_type = row.get("class_type", "")
    session.required_level = row.get("required_level", "Intermediate")
    session.start_datetime = _parse_dt(row["start_datetime"])
    session.duration_mins = int(row.get("duration_mins") or 60)
    session.timezone = row.get("timezone", "UTC")
    session.mode = row.get("mode", "Online")
    session.location = row.get("location") or None
    session.week_start = row.get("week_start") or session.start_datetime.strftime("%Y-%m-%d")
