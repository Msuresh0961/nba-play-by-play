from __future__ import annotations

import re


MILESTONES = {10, 20, 30, 40}


def detect_three_pointer(play):
    if play.get("actionType") == "3pt" and "MISS" not in (play.get("description") or "").upper():
        return f"3-POINTER! {play.get('description')}"
    return None


def detect_dunk(play):
    description = play.get("description") or ""
    if "dunk" in description.lower():
        return f"DUNK! {description}"
    return None


def detect_milestone(play):
    description = play.get("description") or ""
    match = re.search(r"\((\d+) PTS\)", description)
    if match and int(match.group(1)) in MILESTONES:
        return f"MILESTONE! {description}"
    return None


def detect_lead_change(play, previous_scores):
    home = play.get("scoreHome")
    away = play.get("scoreAway")
    if home is None or away is None or previous_scores is None:
        return None
    try:
        home_now = int(home)
        away_now = int(away)
        home_prev = int(previous_scores.get("scoreHome"))
        away_prev = int(previous_scores.get("scoreAway"))
    except (TypeError, ValueError, AttributeError):
        return None
    previous_leader = "home" if home_prev > away_prev else "away" if away_prev > home_prev else None
    current_leader = "home" if home_now > away_now else "away" if away_now > home_now else None
    if previous_leader and current_leader and previous_leader != current_leader:
        return f"LEAD CHANGE! {home_now}-{away_now}"
    return None


def detect_big_run(play, recent_plays):
    if not recent_plays:
        return None

    team_points = {}
    for item in recent_plays[-10:]:
        team = item.get("teamTricode") or item.get("team")
        description = (item.get("description") or "").lower()
        if not team:
            continue
        points = 0
        if "3pt" in description and "miss" not in description:
            points = 3
        elif "2pt" in description and "miss" not in description:
            points = 2
        elif "freethrow" in description and "miss" not in description:
            points = 1
        team_points[team] = team_points.get(team, 0) + points

    for team, points in team_points.items():
        if points >= 10 and len(team_points) > 1:
            return f"10-0 RUN! {team} on fire"
    return None


def detect_events(play, previous_scores=None, recent_plays=None):
    messages = []
    for detector in (
        detect_three_pointer,
        detect_dunk,
        detect_milestone,
    ):
        message = detector(play)
        if message:
            messages.append(message)
    lead_change = detect_lead_change(play, previous_scores)
    if lead_change:
        messages.append(lead_change)
    big_run = detect_big_run(play, recent_plays)
    if big_run:
        messages.append(big_run)
    return messages
