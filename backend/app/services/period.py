"""Schedule period (arbitrary date range) helpers.

Replaces the old fixed-week model: Ops picks any [start_date, end_date],
and every screen filters sessions by Session.start_datetime falling in that
range -- never by a hardcoded Monday-Sunday week. Session.week_start (a
separate, stable data tag) is untouched by any of this; it exists purely so
the matching engine's rolling-fairness lookup stays anchored to each
session's own historical week regardless of what range Ops is currently
reviewing (see matching_engine.py and product spec section 6).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from .. import models


def range_bounds(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    """Inclusive calendar-date range -> [start 00:00, end+1 00:00) bounds,
    consistent with the naive-UTC-instant convention used everywhere else
    (see matching_engine.py / scripts/generate_synthetic_data.py)."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    return start_dt, end_dt


def sessions_in_range(db: DbSession, start_date: str, end_date: str):
    start_dt, end_dt = range_bounds(start_date, end_date)
    return (
        db.query(models.Session)
        .filter(models.Session.start_datetime >= start_dt, models.Session.start_datetime < end_dt)
        .order_by(models.Session.start_datetime)
    )


def assignments_in_range(db: DbSession, start_date: str, end_date: str):
    start_dt, end_dt = range_bounds(start_date, end_date)
    return (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.start_datetime >= start_dt, models.Session.start_datetime < end_dt)
    )


def _dates_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start <= b_end and b_start <= a_end


def find_overlapping_period(
    db: DbSession, start_date: str, end_date: str, exclude_id: str | None = None
) -> models.SchedulePeriod | None:
    """Returns the first existing period that date-overlaps the given range
    and actually has assignments in it (an empty/never-generated period
    stub isn't a real conflict). Finalized periods are returned in
    preference to draft ones, since those need the stricter warning."""
    candidates = db.query(models.SchedulePeriod).all()
    overlapping = [
        p for p in candidates
        if p.id != exclude_id and _dates_overlap(p.start_date, p.end_date, start_date, end_date)
    ]
    if not overlapping:
        return None
    # Only a real conflict if the overlapping period actually has data.
    real = [p for p in overlapping if assignments_in_range(db, p.start_date, p.end_date).count() > 0]
    if not real:
        return None
    finalized = [p for p in real if p.status == "FINALIZED"]
    return finalized[0] if finalized else real[0]


def get_or_create_period(db: DbSession, start_date: str, end_date: str) -> models.SchedulePeriod:
    existing = (
        db.query(models.SchedulePeriod)
        .filter(models.SchedulePeriod.start_date == start_date, models.SchedulePeriod.end_date == end_date)
        .first()
    )
    if existing:
        return existing
    period = models.SchedulePeriod(start_date=start_date, end_date=end_date)
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def get_period_status(db: DbSession, start_date: str, end_date: str) -> dict:
    period = (
        db.query(models.SchedulePeriod)
        .filter(models.SchedulePeriod.start_date == start_date, models.SchedulePeriod.end_date == end_date)
        .first()
    )
    count = assignments_in_range(db, start_date, end_date).count()
    if period is None:
        return {"status": "NONE", "assignment_count": count}
    return {"status": period.status, "assignment_count": count}
