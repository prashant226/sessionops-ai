from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import models
from ..db import get_db
from ..services.matching_engine import _rolling_workload
from ..services.seed import WEEK_START

router = APIRouter(prefix="/smes", tags=["smes"])


class PerformanceRow(BaseModel):
    topic: str
    class_type: str
    sessions_delivered: int
    avg_learner_rating: float
    avg_quality_score: float
    reliability_score: float


class PreferenceOut(BaseModel):
    preferred_topics: list[str]
    preferred_class_types: list[str]
    preferred_start_time: str | None
    preferred_end_time: str | None


class SmeDetailOut(BaseModel):
    sme_id: str
    name: str
    status: str
    timezone: str
    base_location: str
    primary_skills: list[str]
    secondary_skills: list[str]
    expertise_level: str
    max_sessions_per_day: int
    rolling_workload: int
    performance: list[PerformanceRow]
    preferences: PreferenceOut | None


class SmeListItem(BaseModel):
    sme_id: str
    name: str
    status: str
    timezone: str
    base_location: str
    expertise_level: str
    primary_skills: list[str]
    rolling_workload: int


@router.get("", response_model=list[SmeListItem])
def list_smes(db: DbSession = Depends(get_db)):
    smes = db.query(models.Sme).order_by(models.Sme.name).all()
    return [
        SmeListItem(
            sme_id=s.sme_id, name=s.name, status=s.status, timezone=s.timezone, base_location=s.base_location,
            expertise_level=s.expertise_level, primary_skills=s.primary_skills,
            rolling_workload=_rolling_workload(db, s.sme_id, WEEK_START, {}),
        )
        for s in smes
    ]


@router.get("/{sme_id}", response_model=SmeDetailOut)
def get_sme(sme_id: str, db: DbSession = Depends(get_db)):
    s = db.get(models.Sme, sme_id)
    if not s:
        raise HTTPException(status_code=404, detail="SME not found.")
    perf = db.query(models.SmePerformance).filter(models.SmePerformance.sme_id == sme_id).all()
    pref = db.query(models.SmePreference).filter(models.SmePreference.sme_id == sme_id).first()
    return SmeDetailOut(
        sme_id=s.sme_id, name=s.name, status=s.status, timezone=s.timezone, base_location=s.base_location,
        primary_skills=s.primary_skills, secondary_skills=s.secondary_skills, expertise_level=s.expertise_level,
        max_sessions_per_day=s.max_sessions_per_day,
        rolling_workload=_rolling_workload(db, sme_id, WEEK_START, {}),
        performance=[PerformanceRow(
            topic=p.topic, class_type=p.class_type, sessions_delivered=p.sessions_delivered,
            avg_learner_rating=p.avg_learner_rating, avg_quality_score=p.avg_quality_score, reliability_score=p.reliability_score,
        ) for p in perf],
        preferences=PreferenceOut(
            preferred_topics=pref.preferred_topics, preferred_class_types=pref.preferred_class_types,
            preferred_start_time=pref.preferred_start_time, preferred_end_time=pref.preferred_end_time,
        ) if pref else None,
    )
