from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from .. import models, schemas


def candidate_result_to_dict(c) -> dict:
    return {
        "sme_id": c.sme_id,
        "name": c.name,
        "total_score": c.total_score,
        "eligible": c.eligible,
        "elimination_reason": c.elimination_reason,
        "breakdown": {
            "expertise": c.expertise,
            "performance": c.performance,
            "fairness": c.fairness,
            "preference": c.preference,
        },
        "reasons": c.reasons,
        "warnings": c.warnings,
        "rolling_workload": c.rolling_workload,
        "team_average_workload": c.team_average_workload,
    }


EXCEPTION_RULES = {
    "no_qualified_sme": ("Critical", "expertise"),
    "qualified_but_unavailable": ("Critical", "availability"),
    "reassignment_required": ("Critical", "rsvp"),
    "no_replacement_accepted": ("Critical", "unfilled"),
    "fairness_warning": ("Warning", "fairness"),
    "tentative_rsvp": ("Warning", "rsvp"),
    "new_conflict": ("Critical", "availability"),
    "hard_override": ("Warning", "expertise"),
}


def _exception_info(flags: list[str]) -> tuple[str | None, str | None]:
    severity_rank = {"Critical": 2, "Warning": 1}
    best_severity = None
    best_category = None
    for f in flags or []:
        rule = EXCEPTION_RULES.get(f)
        if not rule:
            continue
        severity, category = rule
        if best_severity is None or severity_rank[severity] > severity_rank[best_severity]:
            best_severity, best_category = severity, category
    return best_severity, best_category


def serialize_assignment(db: DbSession, a: models.Assignment, include_candidates: bool = True) -> schemas.AssignmentOut:
    session = a.session or db.get(models.Session, a.session_id)
    sme_name = None
    if a.sme_id:
        sme = db.get(models.Sme, a.sme_id)
        sme_name = sme.name if sme else a.sme_id

    breakdown = None
    candidates: list[schemas.CandidateOut] = []
    snapshot = a.candidates_snapshot or []
    for c in snapshot:
        b = c.get("breakdown", {})
        candidates.append(
            schemas.CandidateOut(
                sme_id=c["sme_id"], name=c["name"], total_score=c["total_score"],
                breakdown=schemas.ScoreBreakdown(
                    expertise=b.get("expertise", 0), performance=b.get("performance", 0),
                    fairness=b.get("fairness", 0), preference=b.get("preference", 0),
                ),
                reasons=c.get("reasons", []), warnings=c.get("warnings", []), eligible=c.get("eligible", True),
                rolling_workload=c.get("rolling_workload", 0), team_average_workload=c.get("team_average_workload", 0),
            )
        )
        if a.sme_id and c["sme_id"] == a.sme_id:
            breakdown = schemas.ScoreBreakdown(
                expertise=b.get("expertise", 0), performance=b.get("performance", 0),
                fairness=b.get("fairness", 0), preference=b.get("preference", 0),
            )

    severity, category = _exception_info(a.flags)

    exception_detail = None
    if "no_qualified_sme" in (a.flags or []):
        exception_detail = {"required_expertise": session.required_level + " " + session.topic, "qualified_count": 0}
    elif "qualified_but_unavailable" in (a.flags or []):
        ineligible_available = [c for c in snapshot if not c.get("eligible", True)]
        exception_detail = {"qualified_count": len(snapshot), "available_count": 0}

    return schemas.AssignmentOut(
        assignment_id=a.assignment_id,
        session=schemas.SessionOut.model_validate(session),
        sme_id=a.sme_id,
        sme_name=sme_name,
        match_score=a.match_score,
        status=a.status,
        rsvp_status=a.rsvp_status,
        reason=a.reason,
        flags=a.flags or [],
        original_sme_id=a.original_sme_id,
        replacement_attempt_count=a.replacement_attempt_count,
        calendar_event_id=a.calendar_event_id,
        breakdown=breakdown,
        candidates=candidates if include_candidates else [],
        activity=[schemas.ActivityOut.model_validate(x) for x in a.activity],
        exception_type=category,
        exception_severity=severity,
        exception_detail=exception_detail,
    )
