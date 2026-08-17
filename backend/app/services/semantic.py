"""Semantic expertise reasoning.

Per the product spec, OpenAI is advisory only: it may nudge the expertise
sub-score by a small bounded amount when a SME's skills are a close semantic
match to the session topic without being an exact string match, and it may
supply the human-readable explanation phrase. It is never consulted for
availability, capacity, timezone, or any hard constraint -- the matching
engine computes eligibility before this module is even called.

In mock mode (default) this uses a deterministic local heuristic so the
product runs with zero external calls. In live mode (INTEGRATION_MODE=live
and OPENAI_API_KEY set) `semantic_expertise_boost` can be swapped for a real
OpenAI call; the call contract (bounded 0-6 point boost, short reason string)
stays identical so the matching engine never has to change.
"""

from __future__ import annotations

from ..config import get_settings

MAX_SEMANTIC_BOOST = 6

_RELATED_TERMS = {
    "python": {"django", "flask", "backend", "programming", "scripting"},
    "sql": {"database", "data analysis", "postgres", "mysql", "query"},
    "kubernetes": {"docker", "devops", "container", "cloud infra"},
    "product strategy": {"product management", "roadmap", "b2b saas", "saas strategy"},
    "system design": {"architecture", "scalability", "backend"},
    "machine learning": {"data science", "ml", "ai", "statistics"},
}


def semantic_expertise_boost(topic: str, primary_skills: list[str], secondary_skills: list[str]) -> tuple[float, str | None]:
    settings = get_settings()
    if settings.is_live and settings.openai_api_key:
        return _live_boost(topic, primary_skills, secondary_skills)
    return _mock_boost(topic, primary_skills, secondary_skills)


def _mock_boost(topic: str, primary_skills: list[str], secondary_skills: list[str]) -> tuple[float, str | None]:
    topic_key = topic.lower()
    skills = {s.lower() for s in (primary_skills or [])} | {s.lower() for s in (secondary_skills or [])}
    related = _RELATED_TERMS.get(topic_key, set())
    overlap = related & skills
    if overlap:
        return MAX_SEMANTIC_BOOST, f"Adjacent expertise in {', '.join(sorted(overlap))}"
    return 0.0, None


def _live_boost(topic: str, primary_skills: list[str], secondary_skills: list[str]) -> tuple[float, str | None]:
    """Placeholder for the real OpenAI call. Wire up once OPENAI_API_KEY is
    supplied: send topic + skills, ask for a 0-6 semantic closeness score and
    a <=8 word reason, clamp the result, and never let this raise -- fall back
    to the mock heuristic on any error so scheduling never depends on the
    LLM being reachable (see spec section 57)."""
    try:
        # from openai import OpenAI
        # client = OpenAI(api_key=get_settings().openai_api_key)
        # ... structured call producing {boost: 0-6, reason: str} ...
        raise NotImplementedError
    except Exception:
        return _mock_boost(topic, primary_skills, secondary_skills)


def explain_recommendation(topic: str, class_type: str, sme_name: str, reasons: list[str]) -> str:
    """Compose the concise natural-language explanation shown in the drawer.
    Built entirely from structured reasons already produced by the matching
    engine -- never fabricated, never a raw model dump (spec section 30)."""
    if not reasons:
        return f"{sme_name} is eligible for this session."
    body = ", ".join(reasons[:-1]) if len(reasons) > 1 else reasons[0]
    tail = f", and {reasons[-1]}" if len(reasons) > 1 else ""
    return f"{sme_name} has {body}{tail}."
