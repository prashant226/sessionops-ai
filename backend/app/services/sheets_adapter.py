"""Google Sheets ingestion adapter.

Mock mode re-seeds the local database from the bundled synthetic fixtures
(services/seed.py), standing in for "read the Sheet tabs". Live mode would
read the seven tabs described in the product spec (Sessions, SME_Profiles,
SME_Performance, Assignment_History, SME_Preferences, Calendar_Events,
Draft_Schedule) via the Sheets API and upsert the same tables, so the rest of
the app never has to know which source it came from.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from ..config import get_settings
from .seed import seed_all


def sync_from_sheets(db: DbSession) -> dict:
    settings = get_settings()
    if settings.is_live and settings.google_sheets_spreadsheet_id:
        return _live_sync(db)
    counts = seed_all(db, reset=True)
    return {"source": "mock_fixtures", **counts}


def _live_sync(db: DbSession) -> dict:
    """Placeholder for the real Sheets API v4 spreadsheets.values.get calls
    against each tab, followed by upserts into the Supabase tables."""
    raise NotImplementedError("Live Google Sheets integration not yet configured")
