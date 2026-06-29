from __future__ import annotations


HIGH_PRIORITY_TYPES = {"lead_change", "scoring_run", "clutch_score", "dunk", "three_pointer"}


def classify_event(play, state):
    event_type = play["type"] or "play"
    description = play["description"].lower()
    tags = []

    if event_type == "3pt" and play["points"] == 3:
        event_type = "three_pointer"
        tags.append("made_shot")
    elif event_type == "2pt" and play["points"] == 2:
        event_type = "made_two"
        tags.append("made_shot")
    elif "dunk" in description:
        event_type = "dunk"
        tags.append("highlight")
    elif event_type == "freethrow":
        tags.append("free_throw")
    elif event_type in {"turnover", "steal", "block", "foul", "timeout", "substitution", "rebound", "jumpball"}:
        tags.append(event_type)

    if state.get("lead_changed"):
        event_type = "lead_change"
        tags.append("swing")

    if state.get("current_run_points", 0) >= 8:
        tags.append("momentum")
        if state.get("current_run_points", 0) >= 10:
            event_type = "scoring_run"

    if _is_clutch(play):
        tags.append("clutch")
        if play["points"] > 0:
            event_type = "clutch_score"

    return {
        "id": play["id"],
        "type": event_type,
        "priority": "high" if event_type in HIGH_PRIORITY_TYPES or "clutch" in tags else "normal",
        "tags": tags,
        "play": play,
        "state": state,
    }


def _is_clutch(play):
    period = play.get("period") or 0
    clock = play.get("clock") or ""
    return period >= 4 and clock.startswith("PT0")
