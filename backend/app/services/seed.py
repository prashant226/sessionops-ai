"""Loads the generated synthetic dataset (data/generated/*.json --
scripts/generate_synthetic_data.py) into the database, standing in for the
"read the Google Sheets tabs" step. See services/sheets_adapter.py for how
this is invoked from the Sync Data action.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy.orm import Session as DbSession

from .. import models

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "data", "generated"))

WEEK_START = "2026-08-24"


def _load(name: str) -> list[dict]:
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _upsert(db: DbSession, model, pk_value, values: dict):
    obj = db.get(model, pk_value)
    if obj is None:
        obj = model()
        db.add(obj)
    for k, v in values.items():
        setattr(obj, k, v)
    return obj


def seed_source_data(db: DbSession) -> dict:
    """Idempotent upsert of everything that stands in for the Google Sheets
    tabs (SME_Profiles, Sessions, SME_Performance, Assignment_History,
    SME_Preferences, Calendar_Events). Safe to call repeatedly (e.g. every
    "Sync Data" click) without disturbing operational state in the
    assignments table."""
    smes = _load("SME_Profiles")
    sessions = _load("Sessions")
    performance = _load("SME_Performance")
    history = _load("Assignment_History")
    preferences = _load("SME_Preferences")
    calendar_events = _load("Calendar_Events")

    for s in smes:
        _upsert(db, models.Sme, s["sme_id"], {
            "sme_id": s["sme_id"], "name": s["name"], "primary_skills": s["primary_skills"],
            "secondary_skills": s["secondary_skills"], "expertise_level": s["expertise_level"],
            "timezone": s["timezone"], "base_location": s["base_location"], "status": s["status"],
            "max_sessions_per_day": s["max_sessions_per_day"], "email": s["email"],
        })
    db.flush()

    for sess in sessions:
        _upsert(db, models.Session, sess["session_id"], {
            "session_id": sess["session_id"], "topic": sess["topic"], "class_type": sess["class_type"],
            "required_level": sess["required_level"], "start_datetime": datetime.fromisoformat(sess["start_datetime"]),
            "duration_mins": sess["duration_mins"], "timezone": sess["timezone"], "mode": sess["mode"],
            "location": sess["location"], "week_start": sess["week_start"],
        })

    db.query(models.SmePerformance).delete()
    for p in performance:
        db.add(models.SmePerformance(sme_id=p["sme_id"], topic=p["topic"], class_type=p["class_type"],
                                      sessions_delivered=p["sessions_delivered"], avg_learner_rating=p["avg_learner_rating"],
                                      avg_quality_score=p["avg_quality_score"], reliability_score=p["reliability_score"]))

    db.query(models.AssignmentHistory).delete()
    for h in history:
        db.add(models.AssignmentHistory(sme_id=h["sme_id"], week_start=h["week_start"], sessions_assigned=h["sessions_assigned"]))

    db.query(models.SmePreference).delete()
    for p in preferences:
        db.add(models.SmePreference(sme_id=p["sme_id"], preferred_topics=p["preferred_topics"],
                                     preferred_class_types=p["preferred_class_types"],
                                     preferred_start_time=p["preferred_start_time"], preferred_end_time=p["preferred_end_time"]))

    db.query(models.CalendarBusyBlock).delete()
    for ev in calendar_events:
        db.add(models.CalendarBusyBlock(event_id=ev["event_id"], sme_id=ev["sme_id"], title=ev["title"],
                                         start_datetime=datetime.fromisoformat(ev["start_datetime"]),
                                         end_datetime=datetime.fromisoformat(ev["end_datetime"])))

    db.commit()
    return {
        "smes": len(smes), "sessions": len(sessions), "performance_rows": len(performance),
        "history_rows": len(history), "preferences": len(preferences), "busy_blocks": len(calendar_events),
    }


def seed_all(db: DbSession, reset: bool = True) -> dict:
    return seed_source_data(db)
