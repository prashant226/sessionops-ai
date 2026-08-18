"""SessionOps AI -- deterministic synthetic dataset generator.

Produces the Google Sheets tab equivalents (Sessions, SME_Profiles,
SME_Performance, Assignment_History, SME_Preferences, Calendar_Events) plus a
synthetic_scenarios.json describing the intentionally engineered edge cases,
as JSON (and CSV mirrors) under data/generated/.

Deterministic: fixed SEED=42, single random.Random instance used in a fixed
call order. Re-running this script produces byte-identical output.

Usage:
    python scripts/generate_synthetic_data.py
"""

from __future__ import annotations

import csv
import json
import os
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEED = 42
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "generated")

WEEK_START = "2026-08-24"  # Mon 24 Aug - 30 Aug 2026, the scheduling week
PRIOR_WEEKS = ["2026-07-27", "2026-08-03", "2026-08-10", "2026-08-17"]  # 4 rolling history weeks

TOPICS = [
    "Python", "SQL", "Machine Learning", "Data Analytics", "Statistics",
    "Data Structures & Algorithms", "Java", "JavaScript", "React", "System Design",
    "Cloud Computing", "DevOps", "Product Management", "Product Strategy",
    "Mock Interviews", "Resume Review", "Behavioral Interviews", "Aptitude",
    "Communication Skills", "Career Coaching",
]
# Popularity weights -- deliberately non-uniform so some topics have 10+
# qualified SMEs and some have 1-2 (spec section 15/16).
TOPIC_WEIGHTS = [10, 9, 6, 5, 4, 6, 5, 5, 4, 6, 5, 4, 4, 3, 8, 3, 3, 2, 2, 2]

CLASS_TYPES = ["Cohort Class", "Doubt Clearing", "Mock Interview", "Workshop", "Office Hours", "Assessment Review"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
LEVEL_WEIGHTS_SME = [22, 45, 33]
LEVEL_WEIGHTS_SESSION = [25, 45, 30]

TIMEZONES = ["Asia/Kolkata", "Europe/London", "America/New_York", "America/Los_Angeles", "Asia/Singapore", "Asia/Dubai"]
TIMEZONE_WEIGHTS = [45, 15, 15, 10, 10, 5]

LOCATIONS = ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", "London", "Singapore", "Dubai", "New York"]
LOCATION_WEIGHTS = [22, 14, 10, 10, 9, 12, 9, 8, 6]

BUSY_TITLES = [
    "Team Meeting", "Client Session", "Cohort Class", "Interview Panel", "Personal Block",
    "Training", "Curriculum Review", "Office Hours", "1:1 Sync", "Planning Session",
]

STATUS_COUNTS = {"Active": 78, "On Leave": 13, "Inactive": 9}  # sums to 100

FIRST_NAMES = [
    "Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Neha", "Karan", "Divya", "Ishaan", "Meera",
    "Arjun", "Sneha", "Aditi", "Rahul", "Kavya", "Nikhil", "Pooja", "Siddharth", "Riya", "Varun",
    "Liam", "Emma", "Noah", "Olivia", "Ethan", "Sophia", "Mason", "Ava", "Lucas", "Mia",
    "James", "Charlotte", "Benjamin", "Amelia", "William", "Isabella", "Henry", "Grace", "Daniel", "Chloe",
    "Wei", "Mei", "Hiroshi", "Yuki", "Jin", "Sooyoung", "Ling", "Tao", "Kenji", "Aiko",
    "Carlos", "Sofia", "Mateo", "Valentina", "Diego", "Camila", "Javier", "Elena", "Andres", "Lucia",
    "Omar", "Layla", "Yusuf", "Amara", "Karim", "Zainab", "Hassan", "Farah", "Tariq", "Noor",
    "Kwame", "Amina", "Chidi", "Zola", "Femi", "Aisha", "Kofi", "Nia", "Tunde", "Imani",
    "Erik", "Freya", "Lars", "Astrid", "Magnus", "Ingrid", "Sven", "Elin", "Anders", "Sigrid",
    "Marco", "Giulia", "Luca", "Chiara", "Matteo", "Alessia", "Paolo", "Bianca", "Fabio", "Rosa",
]
LAST_NAMES = [
    "Sharma", "Verma", "Nair", "Iyer", "Reddy", "Gupta", "Mehta", "Kapoor", "Krishnan", "Das",
    "Rao", "Singh", "Chatterjee", "Bhatt", "Menon", "Pillai", "Joshi", "Malhotra", "Chawla", "Bose",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Wilson", "Taylor",
    "Anderson", "Thomas", "Moore", "Martin", "Clark", "Lewis", "Walker", "Hall", "Young", "King",
    "Chen", "Wang", "Zhang", "Liu", "Yang", "Huang", "Tanaka", "Suzuki", "Kim", "Park",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores",
    "Al-Farsi", "Hassan", "Khalid", "Rahman", "Aziz", "Mansour", "Saleh", "Karim", "Nasser", "Yousef",
    "Okafor", "Mensah", "Diallo", "Osei", "Abara", "Nwosu", "Kamau", "Mwangi", "Adeyemi", "Balewa",
    "Larsen", "Johansson", "Eriksson", "Nilsson", "Andersen", "Berg", "Lindqvist", "Karlsson", "Hansen", "Olsen",
    "Rossi", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci", "Marino", "Greco", "Bruno",
]

# ---------------------------------------------------------------------------
# Reserved IDs for engineered edge cases (assigned deterministically below)
# ---------------------------------------------------------------------------
NO_QUALIFIED_TOPIC = "Cloud Computing"
NO_QUALIFIED_LEVEL = "Advanced"
RARE_CAPACITY_TOPIC = "Aptitude"
RARE_OFFLINE_TOPIC = "Product Management"


def weighted_choice(rng: random.Random, options, weights, k=1, unique=False):
    if unique:
        pool = list(options)
        w = list(weights)
        chosen = []
        for _ in range(k):
            if not pool:
                break
            pick = rng.choices(pool, weights=w, k=1)[0]
            idx = pool.index(pick)
            pool.pop(idx)
            w.pop(idx)
            chosen.append(pick)
        return chosen
    return rng.choices(options, weights=weights, k=k)


def gen_smes(rng: random.Random) -> list[dict]:
    statuses = (["Active"] * STATUS_COUNTS["Active"] + ["On Leave"] * STATUS_COUNTS["On Leave"] + ["Inactive"] * STATUS_COUNTS["Inactive"])
    rng.shuffle(statuses)

    smes = []
    used_names = set()
    for i in range(100):
        sme_id = f"SME{i + 1:03d}"
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 7 + 3) % len(LAST_NAMES)]
        name = f"{first} {last}"
        suffix = 2
        while name in used_names:
            name = f"{first} {last} {suffix}"
            suffix += 1
        used_names.add(name)
        email = f"{first.lower()}.{last.lower().replace(' ', '')}@sessionops-demo.com"

        status = statuses[i]
        level = weighted_choice(rng, LEVELS, LEVEL_WEIGHTS_SME)[0]

        n_primary = rng.choices([1, 2, 3], weights=[45, 40, 15])[0]
        primary = weighted_choice(rng, TOPICS, TOPIC_WEIGHTS, k=n_primary, unique=True)
        remaining = [t for t in TOPICS if t not in primary]
        n_secondary = rng.choices([0, 1, 2], weights=[35, 45, 20])[0]
        remaining_weights = [TOPIC_WEIGHTS[TOPICS.index(t)] for t in remaining]
        secondary = weighted_choice(rng, remaining, remaining_weights, k=n_secondary, unique=True)

        if NO_QUALIFIED_TOPIC in (primary + secondary) and level == "Advanced":
            level = "Intermediate"  # keep the "no qualified SME" scenario intact

        tz = weighted_choice(rng, TIMEZONES, TIMEZONE_WEIGHTS)[0]
        loc = weighted_choice(rng, LOCATIONS, LOCATION_WEIGHTS)[0]
        capacity = rng.choices([2, 3, 4, 5], weights=[35, 35, 20, 10])[0]
        if status != "Active":
            capacity = rng.choice([2, 3])

        smes.append({
            "sme_id": sme_id, "name": name, "email": email,
            "primary_skills": primary, "secondary_skills": secondary,
            "expertise_level": level, "timezone": tz, "base_location": loc,
            "status": status, "max_sessions_per_day": capacity,
        })
    return smes


def apply_reserved_scenarios(rng: random.Random, smes: list[dict]) -> dict:
    """Mutate a handful of SMEs so the required edge cases are guaranteed to
    exist, then return a dict of scenario anchors used later by session/
    performance/history/calendar generation."""
    by_id = {s["sme_id"]: s for s in smes}
    active = [s for s in smes if s["status"] == "Active"]

    # --- Tie scenario: two SMEs identical on every scored dimension for the
    # same topic/class type/level, forcing the deterministic tie-breaker.
    # Uses a deliberately rare topic so the pair isn't outranked by the
    # broader population -- only these two carry it at Advanced level.
    tie_a, tie_b = active[0], active[1]
    for s in (tie_a, tie_b):
        s["primary_skills"] = ["Resume Review"]
        s["secondary_skills"] = [t for t in s["secondary_skills"] if t != "Resume Review"]
        s["expertise_level"] = "Advanced"
        s["timezone"] = "Asia/Kolkata"
        s["base_location"] = "Bangalore"
        s["max_sessions_per_day"] = 3
        s["status"] = "Active"

    # --- Fairness scenario: high performer with high workload vs a slightly
    # lower performer with a much lighter workload, same (rare) topic.
    fair_high, fair_low = active[2], active[3]
    for s in (fair_high, fair_low):
        s["primary_skills"] = ["Behavioral Interviews"]
        s["secondary_skills"] = [t for t in s["secondary_skills"] if t != "Behavioral Interviews"]
        s["expertise_level"] = "Advanced"
        s["status"] = "Active"
        s["timezone"] = "Asia/Kolkata"
        s["base_location"] = "Bangalore"

    # Make sure no other active SME can outrank the engineered pairs on their
    # reserved rare topics.
    for s in active:
        if s in (tie_a, tie_b, fair_high, fair_low):
            continue
        if s["expertise_level"] != "Advanced":
            continue
        for rare_topic in ("Resume Review", "Behavioral Interviews"):
            if rare_topic in s["primary_skills"]:
                s["primary_skills"] = [t for t in s["primary_skills"] if t != rare_topic] or ["Python"]
            if rare_topic in s["secondary_skills"]:
                s["secondary_skills"] = [t for t in s["secondary_skills"] if t != rare_topic]

    # --- Capacity scenario: rare-topic specialist with capacity of exactly 1.
    capacity_sme = active[4]
    capacity_sme["primary_skills"] = [RARE_CAPACITY_TOPIC]
    capacity_sme["secondary_skills"] = []
    capacity_sme["expertise_level"] = "Advanced"
    capacity_sme["max_sessions_per_day"] = 1
    capacity_sme["status"] = "Active"
    capacity_sme["timezone"] = "Asia/Kolkata"

    # --- Offline location mismatch: sole qualified SME is based elsewhere.
    offline_sme = active[5]
    offline_sme["primary_skills"] = [RARE_OFFLINE_TOPIC]
    offline_sme["secondary_skills"] = []
    offline_sme["expertise_level"] = "Advanced"
    offline_sme["base_location"] = "Bangalore"
    offline_sme["status"] = "Active"

    # --- Timezone-preference scenario: technically free, but outside the
    # SME's preferred local working hours (soft factor only).
    tz_pref_sme = active[6]
    tz_pref_sme["primary_skills"] = ["Data Analytics"] + [t for t in tz_pref_sme["primary_skills"] if t != "Data Analytics"][:1]
    tz_pref_sme["expertise_level"] = "Advanced"
    tz_pref_sme["timezone"] = "America/Los_Angeles"
    tz_pref_sme["status"] = "Active"

    # --- Availability conflict scenarios (>=2): top candidate is busy,
    # runner-up is available. Anchors picked from naturally popular topics.
    avail_conflict_1 = [s for s in active if "Python" in s["primary_skills"] and s["expertise_level"] in ("Advanced",)]
    avail_conflict_2 = [s for s in active if "Mock Interviews" in s["primary_skills"] and s["expertise_level"] in ("Advanced", "Intermediate")]

    # --- No-replacement scenario: an intentionally scarce topic/level combo
    # with exactly one truly qualified + available active SME.
    no_replacement_sme = active[7]
    no_replacement_sme["primary_skills"] = ["Career Coaching"]
    no_replacement_sme["secondary_skills"] = []
    no_replacement_sme["expertise_level"] = "Advanced"
    no_replacement_sme["status"] = "Active"
    no_replacement_sme["max_sessions_per_day"] = 3
    # make sure nobody else active carries Career Coaching at Advanced
    for s in active:
        if s is no_replacement_sme:
            continue
        if "Career Coaching" in s["primary_skills"] and s["expertise_level"] == "Advanced":
            s["primary_skills"] = [t for t in s["primary_skills"] if t != "Career Coaching"] or ["Python"]

    return {
        "tie_pair": (tie_a["sme_id"], tie_b["sme_id"]),
        "fairness_pair": (fair_high["sme_id"], fair_low["sme_id"]),
        "capacity_sme": capacity_sme["sme_id"],
        "offline_sme": offline_sme["sme_id"],
        "tz_pref_sme": tz_pref_sme["sme_id"],
        "avail_conflict_pool_1": [s["sme_id"] for s in avail_conflict_1][:4],
        "avail_conflict_pool_2": [s["sme_id"] for s in avail_conflict_2][:4],
        "no_replacement_sme": no_replacement_sme["sme_id"],
        "dropout_pool": [s["sme_id"] for s in active if "Advanced Python".split()[-1] in s["primary_skills"]][:5],
    }


DAY_SESSION_COUNTS = [9, 10, 9, 9, 8, 5, 0]  # Mon..Sun, sums to 50
DURATIONS = [30, 45, 60, 90, 120]
DURATION_WEIGHTS = [15, 20, 30, 25, 10]


def gen_sessions(rng: random.Random, anchors: dict) -> list[dict]:
    sessions = []
    sid = 1
    for day_offset, count in enumerate(DAY_SESSION_COUNTS):
        for _ in range(count):
            topic = weighted_choice(rng, TOPICS, TOPIC_WEIGHTS)[0]
            class_type = rng.choice(CLASS_TYPES)
            level = weighted_choice(rng, LEVELS, LEVEL_WEIGHTS_SESSION)[0]
            tz = weighted_choice(rng, TIMEZONES, TIMEZONE_WEIGHTS)[0]
            hour = rng.randint(9, 18)
            minute = rng.choice([0, 15, 30, 45])
            duration = weighted_choice(rng, DURATIONS, DURATION_WEIGHTS)[0]
            mode = rng.choices(["Online", "Offline"], weights=[85, 15])[0]
            location = weighted_choice(rng, LOCATIONS, LOCATION_WEIGHTS)[0] if mode == "Offline" else None

            sessions.append({
                "session_id": f"S{sid:03d}", "topic": topic, "class_type": class_type,
                "required_level": level, "day_offset": day_offset, "hour": hour, "minute": minute,
                "duration_mins": duration, "timezone": tz, "mode": mode, "location": location,
            })
            sid += 1

    # --- Engineered overrides for specific scenarios -----------------------
    def set_session(idx, **kw):
        sessions[idx].update(kw)

    # C: No qualified SME anywhere (Advanced Cloud Computing)
    set_session(0, topic=NO_QUALIFIED_TOPIC, class_type="Workshop", required_level=NO_QUALIFIED_LEVEL,
                day_offset=1, hour=16, minute=0, duration_mins=90, timezone="Asia/Kolkata", mode="Online", location=None)

    # B1/B2: Availability conflict -- popular topic, top candidate made busy later
    set_session(1, topic="Python", class_type="Mock Interview", required_level="Advanced",
                day_offset=0, hour=10, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)
    set_session(2, topic="Mock Interviews", class_type="Mock Interview", required_level="Intermediate",
                day_offset=2, hour=11, minute=0, duration_mins=45, timezone="Asia/Kolkata", mode="Online", location=None)

    # D: Qualified but unavailable -- career coaching pool all made busy
    set_session(3, topic="Career Coaching", class_type="Office Hours", required_level="Advanced",
                day_offset=3, hour=15, minute=0, duration_mins=45, timezone="Asia/Kolkata", mode="Online", location=None)

    # E: Fairness tradeoff (rare topic so the engineered pair isn't diluted)
    set_session(4, topic="Behavioral Interviews", class_type="Cohort Class", required_level="Advanced",
                day_offset=1, hour=10, minute=0, duration_mins=90, timezone="Asia/Kolkata", mode="Online", location=None)

    # F: Exact tie (rare topic so the engineered pair isn't diluted)
    set_session(5, topic="Resume Review", class_type="Mock Interview", required_level="Advanced",
                day_offset=2, hour=14, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)

    # G1: Cross-timezone hard exclusion (14:00 IST = ~01:30 America/Los_Angeles)
    set_session(6, topic="Data Analytics", class_type="Doubt Clearing", required_level="Advanced",
                day_offset=4, hour=14, minute=0, duration_mins=45, timezone="Asia/Kolkata", mode="Online", location=None)
    # G2: Technically free but outside preferred local hours (soft factor)
    set_session(7, topic="Data Analytics", class_type="Workshop", required_level="Advanced",
                day_offset=2, hour=21, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)

    # H: Capacity constraint -- two same-day sessions for the capacity-1 SME
    set_session(8, topic=RARE_CAPACITY_TOPIC, class_type="Assessment Review", required_level="Advanced",
                day_offset=0, hour=11, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)
    set_session(9, topic=RARE_CAPACITY_TOPIC, class_type="Assessment Review", required_level="Advanced",
                day_offset=0, hour=15, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)

    # I: Offline location mismatch
    set_session(10, topic=RARE_OFFLINE_TOPIC, class_type="Workshop", required_level="Advanced",
                day_offset=3, hour=11, minute=0, duration_mins=90, timezone="Asia/Singapore", mode="Offline", location="Singapore")

    # J/K/L: dropout / replacement / no-replacement demo anchors
    set_session(11, topic="Python", class_type="Mock Interview", required_level="Advanced",
                day_offset=0, hour=14, minute=0, duration_mins=60, timezone="Asia/Kolkata", mode="Online", location=None)
    set_session(12, topic="Career Coaching", class_type="Mock Interview", required_level="Advanced",
                day_offset=4, hour=10, minute=0, duration_mins=45, timezone="Asia/Kolkata", mode="Online", location=None)

    return sessions


def session_start_iso(week_start: str, s: dict) -> str:
    """Wall-clock time is defined in the session's own timezone (s['timezone']).
    Localize it there, convert to a true UTC instant, and store it as a naive
    UTC timestamp -- avoids SQLite's unreliable tz-aware datetime round-trip
    while keeping every stored value an unambiguous absolute instant."""
    base = datetime.strptime(week_start, "%Y-%m-%d")
    local_naive = base + timedelta(days=s["day_offset"], hours=s["hour"], minutes=s["minute"])
    local_aware = local_naive.replace(tzinfo=ZoneInfo(s["timezone"]))
    utc_naive = local_aware.astimezone(timezone.utc).replace(tzinfo=None)
    return utc_naive.strftime("%Y-%m-%dT%H:%M:%S")


def gen_performance(rng: random.Random, smes: list[dict], anchors: dict) -> list[dict]:
    records = []

    def add_record(sme, topic, class_type, sessions_delivered, rating, quality, reliability):
        records.append({
            "sme_id": sme["sme_id"], "topic": topic, "class_type": class_type,
            "sessions_delivered": sessions_delivered,
            "avg_learner_rating": round(rating, 2), "avg_quality_score": round(quality, 1),
            "reliability_score": round(reliability, 1),
        })

    for sme in smes:
        skill_pool = [(t, "primary") for t in sme["primary_skills"]] + [(t, "secondary") for t in sme["secondary_skills"]]
        if not skill_pool:
            continue
        for topic, tier in skill_pool:
            n_class_types = rng.choices([1, 2, 3], weights=[45, 40, 15])[0] if tier == "primary" else rng.choices([1, 2], weights=[70, 30])[0]
            chosen_classes = rng.sample(CLASS_TYPES, k=min(n_class_types, len(CLASS_TYPES)))
            for class_type in chosen_classes:
                if tier == "primary":
                    tier_roll = rng.random()
                    if tier_roll < 0.25:
                        delivered = rng.randint(1, 3)
                    elif tier_roll < 0.75:
                        delivered = rng.randint(4, 15)
                    else:
                        delivered = rng.randint(16, 40)
                    base_quality = rng.uniform(70, 97)
                else:
                    delivered = rng.randint(1, 8)
                    base_quality = rng.uniform(60, 85)

                experience_bonus = min(6, delivered / 6)
                quality = min(100, base_quality + experience_bonus + rng.uniform(-4, 4))
                rating = min(5.0, max(3.0, 3.0 + (quality - 60) / 40 * 2 + rng.uniform(-0.3, 0.3)))
                reliability = min(100, max(70, 75 + experience_bonus + rng.uniform(-5, 8)))

                add_record(sme, topic, class_type, delivered, rating, quality, reliability)

    # --- Tie scenario: force near-identical performance for both candidates
    tie_a, tie_b = anchors["tie_pair"]
    records = [r for r in records if not (r["sme_id"] in (tie_a, tie_b) and r["topic"] == "Resume Review" and r["class_type"] == "Mock Interview")]
    for sid in (tie_a, tie_b):
        records.append({
            "sme_id": sid, "topic": "Resume Review", "class_type": "Mock Interview",
            "sessions_delivered": 14, "avg_learner_rating": 4.60, "avg_quality_score": 87.0, "reliability_score": 93.0,
        })

    # --- Fairness scenario: high performer vs a solid-but-lower performer
    fair_high, fair_low = anchors["fairness_pair"]
    records = [r for r in records if not (r["sme_id"] in (fair_high, fair_low) and r["topic"] == "Behavioral Interviews" and r["class_type"] == "Cohort Class")]
    records.append({"sme_id": fair_high, "topic": "Behavioral Interviews", "class_type": "Cohort Class",
                     "sessions_delivered": 32, "avg_learner_rating": 4.9, "avg_quality_score": 95.0, "reliability_score": 97.0})
    records.append({"sme_id": fair_low, "topic": "Behavioral Interviews", "class_type": "Cohort Class",
                     "sessions_delivered": 9, "avg_learner_rating": 4.5, "avg_quality_score": 84.0, "reliability_score": 90.0})

    # Trim/pad to land in the requested 500-800 range deterministically.
    # Track existing (sme, topic, class_type) combos so padding never creates
    # a duplicate row -- a duplicate would make performance lookups order-
    # dependent and could silently break an engineered scenario (e.g. the
    # forced exact-tie pair) that relies on exactly one row per combo.
    seen = {(r["sme_id"], r["topic"], r["class_type"]) for r in records}
    if len(records) > 800:
        records = records[:800]
    elif len(records) < 500:
        i = 0
        attempts = 0
        active_smes = [s for s in smes if s["primary_skills"]]
        while len(records) < 500 and attempts < 20000:
            attempts += 1
            sme = active_smes[i % len(active_smes)]
            topic = rng.choice(sme["primary_skills"])
            class_type = rng.choice(CLASS_TYPES)
            key = (sme["sme_id"], topic, class_type)
            i += 1
            if key in seen:
                continue
            seen.add(key)
            add_record(sme, topic, class_type, rng.randint(1, 10), rng.uniform(3.5, 4.8), rng.uniform(70, 92), rng.uniform(78, 96))

    return records


LOAD_TIERS = {
    "High": (15, 25),
    "Medium": (8, 15),
    "Low": (2, 8),
}


def gen_history(rng: random.Random, smes: list[dict], anchors: dict) -> list[dict]:
    records = []
    fair_high, fair_low = anchors["fairness_pair"]
    tier_overrides = {fair_high: "High", fair_low: "Low"}

    for sme in smes:
        if sme["sme_id"] in tier_overrides:
            tier = tier_overrides[sme["sme_id"]]
        elif sme["status"] == "Inactive":
            tier = "Low"
        elif sme["status"] == "On Leave":
            tier = rng.choices(["Low", "Medium"], weights=[70, 30])[0]
        else:
            tier = rng.choices(["High", "Medium", "Low"], weights=[20, 50, 30])[0]

        lo, hi = LOAD_TIERS[tier]
        total = rng.randint(lo, hi)
        # split total across 4 weeks with natural variation
        splits = [rng.random() + 0.3 for _ in range(4)]
        s = sum(splits)
        weekly = [max(0, round(total * (x / s))) for x in splits]
        # fix rounding drift
        drift = total - sum(weekly)
        weekly[0] = max(0, weekly[0] + drift)

        for week_start, count in zip(PRIOR_WEEKS, weekly):
            records.append({"sme_id": sme["sme_id"], "week_start": week_start, "sessions_assigned": count})

    # Tie scenario: force identical rolling workload for both candidates so
    # the fairness sub-score matches too, not just performance -- otherwise
    # an incidental workload gap alone would break the "almost identical
    # scores" tie the scenario is meant to demonstrate.
    tie_a, tie_b = anchors["tie_pair"]
    tie_a_weekly = {r["week_start"]: r["sessions_assigned"] for r in records if r["sme_id"] == tie_a}
    records = [r for r in records if r["sme_id"] != tie_b]
    for week_start, count in tie_a_weekly.items():
        records.append({"sme_id": tie_b, "week_start": week_start, "sessions_assigned": count})

    return records


def gen_preferences(rng: random.Random, smes: list[dict], anchors: dict) -> list[dict]:
    records = []
    for sme in smes:
        topics_pool = sme["primary_skills"] + sme["secondary_skills"]
        breadth = rng.choices(["narrow", "broad"], weights=[55, 45])[0]
        if breadth == "narrow":
            preferred_topics = topics_pool[:1] if topics_pool else []
            preferred_classes = rng.sample(CLASS_TYPES, k=1)
            start_h, end_h = rng.choice([(9, 13), (14, 18), (10, 14)])
        else:
            preferred_topics = topics_pool[: rng.randint(1, min(3, len(topics_pool)))] if topics_pool else []
            preferred_classes = rng.sample(CLASS_TYPES, k=rng.randint(2, 3))
            start_h, end_h = 9, 19

        records.append({
            "sme_id": sme["sme_id"],
            "preferred_topics": preferred_topics,
            "preferred_class_types": preferred_classes,
            "preferred_start_time": f"{start_h:02d}:00",
            "preferred_end_time": f"{end_h:02d}:00",
        })

    tz_pref_sme = anchors["tz_pref_sme"]
    for r in records:
        if r["sme_id"] == tz_pref_sme:
            r["preferred_topics"] = ["Data Analytics"]
            r["preferred_class_types"] = ["Workshop"]
            # S008 (21:00 IST) lands at ~08:30 local -- inside working hours (6-22)
            # but outside this preferred window, so it stays hard-eligible while
            # the soft preference score is reduced.
            r["preferred_start_time"] = "10:00"
            r["preferred_end_time"] = "18:00"
    return records


def gen_calendar_events(rng: random.Random, smes: list[dict], sessions: list[dict], anchors: dict) -> list[dict]:
    events = []
    eid = 1
    sme_by_id = {s["sme_id"]: s for s in smes}

    def add_event(sme_id, title, day_offset, hour, minute, duration, tz_name=None):
        """day_offset/hour/minute are wall-clock local time -- in the SME's
        own timezone by default, unless tz_name is given explicitly (used
        when blocking a session's own timezone, e.g. an injected conflict)."""
        nonlocal eid
        tz_name = tz_name or sme_by_id[sme_id]["timezone"]
        base = datetime.strptime(WEEK_START, "%Y-%m-%d")
        local_naive = base + timedelta(days=day_offset, hours=hour, minutes=minute)
        local_aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
        start_utc = local_aware.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = start_utc + timedelta(minutes=duration)
        events.append({
            "event_id": f"EVT{eid:04d}", "sme_id": sme_id, "title": title,
            "start_datetime": start_utc.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_datetime": end_utc.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        eid += 1

    for sme in smes:
        n_events = rng.randint(3, 8)
        used_slots = []
        attempts = 0
        placed = 0
        while placed < n_events and attempts < n_events * 4:
            attempts += 1
            day_offset = rng.randint(0, 5)  # Mon-Sat
            hour = rng.randint(8, 19)
            minute = rng.choice([0, 30])
            duration = rng.choice([30, 45, 60, 90])
            overlap = any(day_offset == d and abs((hour * 60 + minute) - (h * 60 + m)) < max(duration, dur) for d, h, m, dur in used_slots)
            if overlap:
                continue
            used_slots.append((day_offset, hour, minute, duration))
            title = rng.choice(BUSY_TITLES)
            add_event(sme["sme_id"], title, day_offset, hour, minute, duration)
            placed += 1

    sessions_by_id = {s["session_id"]: s for s in sessions}

    # The general random population above can accidentally collide with a
    # reserved scenario's own session for an SME that scenario needs to stay
    # available. Drop any such accidental overlaps before applying the
    # intentional conflict injections below.
    must_stay_available = [
        (anchors["no_replacement_sme"], "S013"),
        (anchors["capacity_sme"], "S009"),
        (anchors["tie_pair"][0], "S006"), (anchors["tie_pair"][1], "S006"),
        (anchors["fairness_pair"][0], "S005"), (anchors["fairness_pair"][1], "S005"),
        (anchors["tz_pref_sme"], "S007"), (anchors["tz_pref_sme"], "S008"),
    ]

    def _overlaps(ev, session_id):
        s = sessions_by_id[session_id]
        s_start = datetime.fromisoformat(session_start_iso(WEEK_START, s))
        s_end = s_start + timedelta(minutes=s["duration_mins"])
        e_start = datetime.fromisoformat(ev["start_datetime"])
        e_end = datetime.fromisoformat(ev["end_datetime"])
        return s_start < e_end and s_end > e_start

    for sme_id, session_id in must_stay_available:
        events[:] = [ev for ev in events if not (ev["sme_id"] == sme_id and _overlaps(ev, session_id))]

    def block_sme_for_session(sme_id, session_id, title="Client Session"):
        s = sessions_by_id[session_id]
        # The session's own wall-clock hour is defined in the session's
        # timezone, not the SME's -- localize with that tz so the busy block
        # lands on the same real-world instant as the session.
        add_event(sme_id, title, s["day_offset"], s["hour"], s["minute"], s["duration_mins"], tz_name=s["timezone"])

    # B1/B2 -- block the strongest candidate(s) at the exact session time
    for sme_id in anchors["avail_conflict_pool_1"][:1]:
        block_sme_for_session(sme_id, "S002", "Interview Panel")
    for sme_id in anchors["avail_conflict_pool_2"][:1]:
        block_sme_for_session(sme_id, "S003", "Cohort Class")

    # D -- block every qualified Career Coaching SME for S004
    no_replacement_sme = anchors["no_replacement_sme"]
    for sme in smes:
        if sme["status"] == "Active" and "Career Coaching" in sme["primary_skills"]:
            block_sme_for_session(sme["sme_id"], "S004", "Client Session")

    return events


def build_scenarios(anchors: dict) -> list[dict]:
    return [
        {"scenario_id": "SCN_NORMAL_01", "name": "Normal assignment, many candidates", "session_id": "S015",
         "expected_behavior": "Multiple qualified, available SMEs exist; agent ranks and selects the highest-scoring one."},
        {"scenario_id": "SCN_AVAILABILITY_01", "name": "Qualified SME busy, runner-up available", "session_id": "S002",
         "expected_behavior": "Busy top candidate excluded by the hard calendar-conflict rule; next eligible candidate recommended."},
        {"scenario_id": "SCN_AVAILABILITY_02", "name": "Qualified SME busy, runner-up available", "session_id": "S003",
         "expected_behavior": "Busy top candidate excluded by the hard calendar-conflict rule; next eligible candidate recommended."},
        {"scenario_id": "SCN_NO_QUALIFIED_01", "name": "No qualified SME", "session_id": "S001",
         "expected_behavior": "No active SME holds Advanced Cloud Computing; session is UNFILLED with a Critical, no-qualified-SME exception."},
        {"scenario_id": "SCN_QUALIFIED_UNAVAILABLE_01", "name": "Qualified but unavailable", "session_id": "S004",
         "expected_behavior": "Every qualified Career Coaching SME has a calendar conflict at this time; session is UNFILLED with a Critical, qualified-but-unavailable exception."},
        {"scenario_id": "SCN_FAIRNESS_01", "name": "Expertise vs. workload tradeoff", "session_id": "S005",
         "expected_behavior": f"{anchors['fairness_pair'][0]} scores highest on expertise/performance but carries a heavy rolling workload; {anchors['fairness_pair'][1]} is close behind with a much lighter workload. Fairness narrows the gap without automatically winning."},
        {"scenario_id": "SCN_TIE_01", "name": "Exact scoring tie", "session_id": "S006",
         "expected_behavior": f"{anchors['tie_pair'][0]} and {anchors['tie_pair'][1]} are identical on expertise, performance, fairness and preference; deterministic tie-break order resolves it."},
        {"scenario_id": "SCN_TIMEZONE_01", "name": "Cross-timezone hard exclusion", "session_id": "S007",
         "expected_behavior": f"{anchors['tz_pref_sme']} would be qualified, but the session falls outside working hours in their local timezone; hard-excluded."},
        {"scenario_id": "SCN_TIMEZONE_02", "name": "Free but outside preferred hours", "session_id": "S008",
         "expected_behavior": f"{anchors['tz_pref_sme']} is technically available (within working hours) but the session falls outside their stated preference window; preference score reduced, not excluded."},
        {"scenario_id": "SCN_CAPACITY_01", "name": "Daily capacity reached", "session_id": "S010",
         "expected_behavior": f"{anchors['capacity_sme']} has max_sessions_per_day=1 and is already assigned S009 earlier that day; excluded from S010 by the hard capacity rule."},
        {"scenario_id": "SCN_OFFLINE_LOCATION_01", "name": "Offline location mismatch", "session_id": "S011",
         "expected_behavior": f"{anchors['offline_sme']} is the only qualified SME but is based in Bangalore while the session is Offline in Singapore; hard-excluded on location."},
        {"scenario_id": "SCN_DROPOUT_01", "name": "Original SME declines, replacement accepts", "session_id": "S012",
         "expected_behavior": "Approve the AI recommendation, simulate an RSVP decline, confirm a replacement is recommended and can be invited and accepted."},
        {"scenario_id": "SCN_NO_REPLACEMENT_01", "name": "Decline with no available replacement", "session_id": "S013",
         "expected_behavior": f"{anchors['no_replacement_sme']} is the sole qualified+available Career Coaching SME; simulating a decline leaves zero replacement candidates, producing a Critical unfilled exception."},
    ]


def to_full_records(sessions: list[dict]) -> list[dict]:
    out = []
    for s in sessions:
        out.append({
            "session_id": s["session_id"], "topic": s["topic"], "class_type": s["class_type"],
            "required_level": s["required_level"], "start_datetime": session_start_iso(WEEK_START, s),
            "duration_mins": s["duration_mins"], "timezone": s["timezone"], "mode": s["mode"], "location": s["location"],
            "week_start": WEEK_START,
        })
    return out


def write_json(name: str, data) -> str:
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def write_csv(name: str, rows: list[dict]) -> str:
    """List-valued fields (skills, preferred topics, ...) are written as a
    plain '; '-joined string, not JSON -- this is what ends up in a Google
    Sheets cell after import, and it's what services/sheets_adapter.py's
    _split_list() expects when reading a live Sheet back."""
    path = os.path.join(OUT_DIR, f"{name}.csv")
    if not rows:
        return path
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            row = {k: ("; ".join(v) if isinstance(v, list) else v) for k, v in r.items()}
            writer.writerow(row)
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = random.Random(SEED)

    smes = gen_smes(rng)
    anchors = apply_reserved_scenarios(rng, smes)
    sessions_raw = gen_sessions(rng, anchors)
    sessions = to_full_records(sessions_raw)
    performance = gen_performance(rng, smes, anchors)
    history = gen_history(rng, smes, anchors)
    preferences = gen_preferences(rng, smes, anchors)
    calendar_events = gen_calendar_events(rng, smes, sessions_raw, anchors)
    scenarios = build_scenarios(anchors)

    sme_out = [{k: v for k, v in s.items()} for s in smes]

    write_json("SME_Profiles", sme_out)
    write_json("Sessions", sessions)
    write_json("SME_Performance", performance)
    write_json("Assignment_History", history)
    write_json("SME_Preferences", preferences)
    write_json("Calendar_Events", calendar_events)
    write_json("synthetic_scenarios", scenarios)
    write_json("_anchors", anchors)  # internal debug reference, not a Sheet tab

    write_csv("SME_Profiles", sme_out)
    write_csv("Sessions", sessions)
    write_csv("SME_Performance", performance)
    write_csv("Assignment_History", history)
    write_csv("SME_Preferences", preferences)
    write_csv("Calendar_Events", calendar_events)

    status_counts = {}
    for s in smes:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    print("Dataset generated successfully.\n")
    print(f"SMEs: {len(smes)} ({', '.join(f'{k}: {v}' for k, v in status_counts.items())})")
    print(f"Sessions: {len(sessions)}")
    print(f"Performance records: {len(performance)}")
    print(f"Assignment history records: {len(history)}")
    print(f"Preference records: {len(preferences)}")
    print(f"Calendar events: {len(calendar_events)}")
    print(f"Scenario metadata entries: {len(scenarios)}")
    print(f"\nOutput directory: {OUT_DIR}")


if __name__ == "__main__":
    main()
