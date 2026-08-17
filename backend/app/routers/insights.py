from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from .. import models
from ..db import get_db
from ..services.matching_engine import _rolling_workload

router = APIRouter(prefix="/insights", tags=["insights"])


class Metric(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str  # "percent" | "minutes" | "count"
    definition: str
    calculation: str
    why_it_matters: str


class WorkloadPoint(BaseModel):
    sme_id: str
    name: str
    rolling_workload: int


class InsightsOut(BaseModel):
    efficiency: list[Metric]
    ai_quality: list[Metric]
    scheduling_quality: list[Metric]
    workload: list[WorkloadPoint]
    team_average_workload: float


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


def _minutes_between(a_ts, b_ts) -> float:
    return abs((b_ts - a_ts).total_seconds()) / 60


@router.get("", response_model=InsightsOut)
def get_insights(week_start: str, db: DbSession = Depends(get_db)):
    rows = (
        db.query(models.Assignment)
        .join(models.Session, models.Assignment.session_id == models.Session.session_id)
        .filter(models.Session.week_start == week_start)
        .all()
    )
    total = len(rows)
    recommended = [a for a in rows if a.candidates_snapshot]
    decided = [a for a in rows if a.status not in (models.AssignmentStatus.PENDING_REVIEW.value, models.AssignmentStatus.DRAFT.value)]

    accepted_as_is = sum(
        1 for a in recommended
        if a.status in (models.AssignmentStatus.APPROVED.value, models.AssignmentStatus.CONFIRMED.value, models.AssignmentStatus.FINALIZED.value)
        and not any(act.actor == "Ops" and ("changed" in act.message or "overrode" in act.message) for act in a.activity)
    )
    overridden = sum(1 for a in rows if a.status == models.AssignmentStatus.OVERRIDDEN.value)
    ever_reassigned = sum(1 for a in rows if a.original_sme_id or a.status in (models.AssignmentStatus.REASSIGNMENT_REQUIRED.value, models.AssignmentStatus.REASSIGNED.value))
    unfilled = sum(1 for a in rows if a.status == models.AssignmentStatus.UNFILLED.value)
    conflicts = sum(1 for a in rows if set(a.flags or []) & {"qualified_but_unavailable", "new_conflict"})

    invites_sent = 0
    declines = 0
    scheduling_times = []
    review_times = []
    for a in rows:
        acts = sorted(a.activity, key=lambda x: x.timestamp)
        rec_ts = next((x.timestamp for x in acts if x.actor == "AI" and "recommended" in x.message), None)
        decision_ts = next((x.timestamp for x in acts if x.actor == "Ops" and any(w in x.message for w in ("approved", "changed", "rejected", "overrode"))), None)
        resolved_ts = next((x.timestamp for x in reversed(acts) if "accepted the invitation" in x.message or x.actor == "System" and "Calendar invitation sent" in x.message), None)
        if rec_ts and decision_ts:
            review_times.append(_minutes_between(rec_ts, decision_ts))
        if rec_ts and resolved_ts:
            scheduling_times.append(_minutes_between(rec_ts, resolved_ts))
        invites_sent += sum(1 for x in acts if "invitation sent" in x.message)
        declines += sum(1 for x in acts if "declined the invitation" in x.message)

    avg_scheduling_time = round(sum(scheduling_times) / len(scheduling_times), 1) if scheduling_times else None
    avg_review_time = round(sum(review_times) / len(review_times), 1) if review_times else None

    efficiency = [
        Metric(key="avg_scheduling_time", label="Average Scheduling Time", value=avg_scheduling_time, unit="minutes",
               definition="Time from the AI recommendation being generated to the session being fully resolved (invited and accepted).",
               calculation="Mean of (resolution timestamp - recommendation timestamp) across resolved assignments.",
               why_it_matters="Shorter scheduling time means learners get confirmed sessions sooner and Ops spends less time per session."),
        Metric(key="manual_review_time", label="Manual Review Time", value=avg_review_time, unit="minutes",
               definition="Time from the AI recommendation appearing to Ops taking a decision (approve, edit, or reject).",
               calculation="Mean of (decision timestamp - recommendation timestamp) across reviewed assignments.",
               why_it_matters="Tracks how much human review time each recommendation actually requires."),
        Metric(key="fill_rate", label="Fill Rate", value=_pct(total - unfilled, total), unit="percent",
               definition="Share of this week's sessions that ended up with an assigned SME.",
               calculation="(Total sessions - Unfilled sessions) / Total sessions.",
               why_it_matters="The most direct measure of whether the week's curriculum can actually run as planned."),
    ]

    ai_quality = [
        Metric(key="acceptance_rate", label="AI Recommendation Acceptance Rate", value=_pct(accepted_as_is, len(recommended)), unit="percent",
               definition="Percentage of AI recommendations approved without changing the suggested SME.",
               calculation="Approved recommendations / Total recommendations.",
               why_it_matters="Higher acceptance suggests stronger recommendation quality."),
        Metric(key="override_rate", label="Override Rate", value=_pct(overridden, total), unit="percent",
               definition="Percentage of assignments where Ops assigned an SME who violated a hard constraint.",
               calculation="Overridden assignments / Total sessions.",
               why_it_matters="A rising override rate can mean the matching rules are too strict, or data quality issues are forcing exceptions."),
        Metric(key="reassignment_rate", label="Reassignment Rate", value=_pct(ever_reassigned, total), unit="percent",
               definition="Percentage of sessions that required at least one reassignment after the original SME declined or dropped out.",
               calculation="Sessions that entered Reassignment Required / Total sessions.",
               why_it_matters="High reassignment rates point to unreliable SMEs or overly ambitious initial matches."),
    ]

    scheduling_quality = [
        Metric(key="conflict_rate", label="Conflict Rate", value=_pct(conflicts, total), unit="percent",
               definition="Percentage of sessions where every qualified SME had a calendar conflict at the required time.",
               calculation="Sessions flagged qualified-but-unavailable or with a newly discovered conflict / Total sessions.",
               why_it_matters="High conflict rates suggest the SME pool is stretched too thin at certain times."),
        Metric(key="unfilled_rate", label="Unfilled Rate", value=_pct(unfilled, total), unit="percent",
               definition="Percentage of sessions with no SME assigned at all by the end of the week.",
               calculation="Unfilled sessions / Total sessions.",
               why_it_matters="Every unfilled session is a session a learner does not get."),
        Metric(key="rsvp_decline_rate", label="RSVP Decline Rate", value=_pct(declines, invites_sent), unit="percent",
               definition="Percentage of calendar invitations that were declined by the invited SME.",
               calculation="Declined invitations / Total invitations sent (including replacements).",
               why_it_matters="A high decline rate signals either SME overcommitment or recommendations that don't fit SME availability well."),
    ]

    active_smes = db.query(models.Sme).filter(models.Sme.status == models.SmeStatus.ACTIVE.value).all()
    workload_points = [
        WorkloadPoint(sme_id=s.sme_id, name=s.name, rolling_workload=_rolling_workload(db, s.sme_id, week_start, {}))
        for s in active_smes
    ]
    team_avg = round(sum(w.rolling_workload for w in workload_points) / len(workload_points), 1) if workload_points else 0.0
    workload_points.sort(key=lambda w: -w.rolling_workload)

    return InsightsOut(efficiency=efficiency, ai_quality=ai_quality, scheduling_quality=scheduling_quality,
                        workload=workload_points, team_average_workload=team_avg)
