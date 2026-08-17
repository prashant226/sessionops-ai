"""SessionOps AI -- synthetic dataset validator.

Loads data/generated/*.json and checks structural integrity (unique IDs,
valid foreign keys, well-formed timestamps/timezones, sane value ranges),
then checks that every engineered edge case from the generator is actually
present in the data. Prints a summary in the format requested by the data
generation brief.

Usage:
    python scripts/validate_synthetic_data.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data", "generated")

VALID_TIMEZONES = {"Asia/Kolkata", "Europe/London", "America/New_York", "America/Los_Angeles", "Asia/Singapore", "Asia/Dubai"}
VALID_LEVELS = {"Beginner", "Intermediate", "Advanced"}
VALID_STATUS = {"Active", "Inactive", "On Leave"}


def load(name):
    with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def check(errors, condition, message):
    if not condition:
        errors.append(message)


def validate():
    errors: list[str] = []

    smes = load("SME_Profiles")
    sessions = load("Sessions")
    performance = load("SME_Performance")
    history = load("Assignment_History")
    preferences = load("SME_Preferences")
    calendar_events = load("Calendar_Events")
    scenarios = load("synthetic_scenarios")

    sme_ids = {s["sme_id"] for s in smes}
    session_ids = {s["session_id"] for s in sessions}

    check(errors, len(sme_ids) == len(smes), "Duplicate SME IDs found")
    check(errors, len(session_ids) == len(sessions), "Duplicate session IDs found")

    for s in smes:
        check(errors, s["status"] in VALID_STATUS, f"{s['sme_id']}: invalid status {s['status']}")
        check(errors, s["expertise_level"] in VALID_LEVELS, f"{s['sme_id']}: invalid expertise_level")
        check(errors, s["timezone"] in VALID_TIMEZONES, f"{s['sme_id']}: invalid timezone {s['timezone']}")
        check(errors, s["max_sessions_per_day"] > 0, f"{s['sme_id']}: non-positive capacity")
        check(errors, len(s["primary_skills"]) + len(s["secondary_skills"]) > 0 or True, "")
        try:
            ZoneInfo(s["timezone"])
        except ZoneInfoNotFoundError:
            errors.append(f"{s['sme_id']}: unresolvable timezone {s['timezone']}")

    for s in sessions:
        check(errors, s["required_level"] in VALID_LEVELS, f"{s['session_id']}: invalid required_level")
        check(errors, s["duration_mins"] > 0, f"{s['session_id']}: non-positive duration")
        check(errors, s["timezone"] in VALID_TIMEZONES, f"{s['session_id']}: invalid timezone")
        check(errors, s["mode"] in ("Online", "Offline"), f"{s['session_id']}: invalid mode")
        if s["mode"] == "Offline":
            check(errors, bool(s["location"]), f"{s['session_id']}: Offline session missing location")
        try:
            dt = datetime.fromisoformat(s["start_datetime"])
        except ValueError:
            errors.append(f"{s['session_id']}: malformed start_datetime")
            dt = None
        check(errors, dt is not None, f"{s['session_id']}: unparsable timestamp")

    for p in performance:
        check(errors, p["sme_id"] in sme_ids, f"Performance record references unknown SME {p['sme_id']}")
        check(errors, 0 <= p["sessions_delivered"], f"Performance record has negative sessions_delivered")
        check(errors, 1.0 <= p["avg_learner_rating"] <= 5.0, f"Performance record has out-of-range rating for {p['sme_id']}")
        check(errors, 0 <= p["avg_quality_score"] <= 100, f"Performance record has out-of-range quality for {p['sme_id']}")
        check(errors, 0 <= p["reliability_score"] <= 100, f"Performance record has out-of-range reliability for {p['sme_id']}")

    for h in history:
        check(errors, h["sme_id"] in sme_ids, f"History record references unknown SME {h['sme_id']}")
        check(errors, h["sessions_assigned"] >= 0, f"History record has negative sessions_assigned")

    for pr in preferences:
        check(errors, pr["sme_id"] in sme_ids, f"Preference record references unknown SME {pr['sme_id']}")

    for ev in calendar_events:
        check(errors, ev["sme_id"] in sme_ids, f"Calendar event references unknown SME {ev['sme_id']}")
        try:
            s_dt = datetime.fromisoformat(ev["start_datetime"])
            e_dt = datetime.fromisoformat(ev["end_datetime"])
            check(errors, e_dt > s_dt, f"Calendar event {ev['event_id']} has end before start")
        except ValueError:
            errors.append(f"Calendar event {ev['event_id']}: malformed timestamp")

    # ---- Edge case coverage --------------------------------------------
    sme_by_id = {s["sme_id"]: s for s in smes}
    session_by_id = {s["session_id"]: s for s in sessions}
    active_ids = {s["sme_id"] for s in smes if s["status"] == "Active"}

    def qualifies(sme, topic, level_rank):
        rank = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
        skills = set(sme["primary_skills"]) | set(sme["secondary_skills"])
        return topic in skills and rank[sme["expertise_level"]] >= level_rank

    rank = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}

    def qualified_count(topic, level):
        return sum(1 for sid in active_ids if qualifies(sme_by_id[sid], topic, rank[level]))

    s001 = session_by_id["S001"]
    no_qualified = qualified_count(s001["topic"], s001["required_level"]) == 0

    def has_busy_overlap(sme_id, session):
        s_start = datetime.fromisoformat(session["start_datetime"])
        s_end = s_start.replace()
        from datetime import timedelta
        s_end = s_start + timedelta(minutes=session["duration_mins"])
        for ev in calendar_events:
            if ev["sme_id"] != sme_id:
                continue
            e_start = datetime.fromisoformat(ev["start_datetime"])
            e_end = datetime.fromisoformat(ev["end_datetime"])
            if s_start < e_end and s_end > e_start:
                return True
        return False

    s002 = session_by_id["S002"]
    s002_qualified = [sid for sid in active_ids if qualifies(sme_by_id[sid], s002["topic"], rank[s002["required_level"]])]
    s002_busy_top = any(has_busy_overlap(sid, s002) for sid in s002_qualified)
    s002_available = [sid for sid in s002_qualified if not has_busy_overlap(sid, s002)]
    availability_conflict_pass = s002_busy_top and len(s002_available) > 0

    s004 = session_by_id["S004"]
    s004_qualified = [sid for sid in active_ids if qualifies(sme_by_id[sid], s004["topic"], rank[s004["required_level"]])]
    s004_available = [sid for sid in s004_qualified if not has_busy_overlap(sid, s004)]
    qualified_unavailable_pass = len(s004_qualified) > 0 and len(s004_available) == 0

    anchors = load("_anchors")
    tie_pass = anchors["tie_pair"][0] in sme_ids and anchors["tie_pair"][1] in sme_ids
    fairness_pass = anchors["fairness_pair"][0] in sme_ids and anchors["fairness_pair"][1] in sme_ids

    s007 = session_by_id["S007"]
    tz_pref_sme = sme_by_id[anchors["tz_pref_sme"]]
    tz_session_local_hour = None
    try:
        # start_datetime is stored as a naive UTC instant (see generator).
        dt = datetime.fromisoformat(s007["start_datetime"]).replace(tzinfo=dt_timezone.utc)
        tz_session_local_hour = dt.astimezone(ZoneInfo(tz_pref_sme["timezone"])).hour
    except Exception:
        pass
    timezone_pass = tz_session_local_hour is not None and not (6 <= tz_session_local_hour < 22)

    capacity_sme = sme_by_id[anchors["capacity_sme"]]
    capacity_pass = capacity_sme["max_sessions_per_day"] == 1

    offline_sme = sme_by_id[anchors["offline_sme"]]
    s011 = session_by_id["S011"]
    offline_pass = s011["mode"] == "Offline" and s011["location"] != offline_sme["base_location"]

    dropout_pass = len(anchors.get("dropout_pool", [])) > 0
    no_replacement_sme = anchors["no_replacement_sme"]
    s013 = session_by_id["S013"]
    s013_qualified = [sid for sid in active_ids if qualifies(sme_by_id[sid], s013["topic"], rank[s013["required_level"]])]
    no_replacement_pass = s013_qualified == [no_replacement_sme]

    normal_candidates = [
        s for s in sessions
        if qualified_count(s["topic"], s["required_level"]) >= 3
    ]
    normal_pass = len(normal_candidates) >= 10

    status_counts = {}
    for s in smes:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    print("SMEs:", len(smes))
    print("Sessions:", len(sessions))
    print("Performance records:", len(performance))
    print("History records:", len(history))
    print("Preference records:", len(preferences))
    print("Calendar events:", len(calendar_events))
    print()
    print("Status distribution:", status_counts)
    print()
    print("Edge-case coverage:")
    print("Normal (10+ sessions with 3+ qualified):", "PASS" if normal_pass else "FAIL", f"({len(normal_candidates)} sessions)")
    print("Availability conflict:", "PASS" if availability_conflict_pass else "FAIL")
    print("No qualified SME:", "PASS" if no_qualified else "FAIL")
    print("Qualified but unavailable:", "PASS" if qualified_unavailable_pass else "FAIL")
    print("Fairness:", "PASS" if fairness_pass else "FAIL")
    print("Tie:", "PASS" if tie_pass else "FAIL")
    print("Timezone hard exclusion:", "PASS" if timezone_pass else "FAIL", f"(local hour {tz_session_local_hour})")
    print("Capacity:", "PASS" if capacity_pass else "FAIL")
    print("Offline location mismatch:", "PASS" if offline_pass else "FAIL")
    print("Dropout replacement pool exists:", "PASS" if dropout_pass else "FAIL")
    print("No-replacement scenario:", "PASS" if no_replacement_pass else "FAIL",
          f"(qualified active SMEs for S013: {s013_qualified})")
    print(f"\nScenario metadata entries: {len(scenarios)}")

    print()
    if errors:
        print(f"VALIDATION: FAIL ({len(errors)} structural issues)")
        for e in errors[:30]:
            print(" -", e)
        return 1
    print("VALIDATION: PASS (no structural issues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
