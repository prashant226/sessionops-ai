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


_client = None
_live_boost_cache: dict[tuple, tuple[float, str | None]] = {}


def _openai_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def _live_boost(topic: str, primary_skills: list[str], secondary_skills: list[str]) -> tuple[float, str | None]:
    """Asks OpenAI for a bounded 0-6 semantic-closeness nudge and a short
    reason phrase when a SME's skills aren't an exact string match to the
    session topic. Never raises -- any failure (network, quota, malformed
    response) falls back to the local heuristic so core scheduling never
    depends on the LLM being reachable (spec section 57). Cached per
    (topic, skill set) for the life of the process -- the same SME/topic
    combination recurs across many sessions in a single draft generation
    run, and there's no reason to re-ask the model the same question."""
    cache_key = (topic.lower(), tuple(sorted(s.lower() for s in primary_skills + secondary_skills)))
    if cache_key in _live_boost_cache:
        return _live_boost_cache[cache_key]
    try:
        client = _openai_client()
        skills = ", ".join(primary_skills + secondary_skills) or "none listed"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You score how semantically close a subject-matter expert's skills are to a "
                        "session topic, for adjacent (non-exact-match) expertise only. Respond with "
                        "compact JSON: {\"boost\": <integer 0-6>, \"reason\": \"<8 words or fewer>\"}. "
                        "boost=0 if there is no meaningful semantic relationship. Never invent facts "
                        "about the SME; only reason about the topic/skill names given."
                    ),
                },
                {"role": "user", "content": f"Session topic: {topic}\nSME skills: {skills}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=60,
            timeout=6,
        )
        import json as _json

        parsed = _json.loads(response.choices[0].message.content)
        boost = max(0.0, min(MAX_SEMANTIC_BOOST, float(parsed.get("boost", 0))))
        reason = str(parsed.get("reason") or "").strip()[:80] or None
        result = (0.0, None) if boost <= 0 else (boost, reason)
    except Exception:
        result = _mock_boost(topic, primary_skills, secondary_skills)
    _live_boost_cache[cache_key] = result
    return result


def explain_recommendation(topic: str, class_type: str, sme_name: str, reasons: list[str]) -> str:
    """Compose the concise natural-language explanation shown in the drawer.
    Built entirely from structured reasons already produced by the matching
    engine -- never fabricated, never a raw model dump (spec section 30)."""
    if not reasons:
        return f"{sme_name} is eligible for this session."
    body = ", ".join(reasons[:-1]) if len(reasons) > 1 else reasons[0]
    tail = f", and {reasons[-1]}" if len(reasons) > 1 else ""
    return f"{sme_name} has {body}{tail}."
