from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import models
from ..db import get_db

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    type: str  # "session" | "sme"
    id: str
    label: str
    sublabel: str


@router.get("", response_model=list[SearchResult])
def search(q: str, db: DbSession = Depends(get_db)):
    q = q.strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    results: list[SearchResult] = []

    sessions = (
        db.query(models.Session)
        .filter((models.Session.session_id.ilike(like)) | (models.Session.topic.ilike(like)))
        .limit(10)
        .all()
    )
    for s in sessions:
        results.append(SearchResult(type="session", id=s.session_id, label=f"{s.session_id} · {s.topic}", sublabel=f"{s.class_type} · {s.required_level}"))

    smes = db.query(models.Sme).filter(models.Sme.name.ilike(like)).limit(10).all()
    for s in smes:
        results.append(SearchResult(type="sme", id=s.sme_id, label=s.name, sublabel=f"{s.status} · {s.base_location}"))

    return results
