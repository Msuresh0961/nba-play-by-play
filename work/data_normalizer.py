from __future__ import annotations


def normalize_play(raw):
    description = raw.get("description") or ""
    action_type = (raw.get("actionType") or "").lower()

    return {
        "id": raw.get("actionNumber"),
        "game_id": raw.get("gameId"),
        "type": action_type,
        "sub_type": raw.get("subType") or raw.get("descriptor") or "",
        "description": description,
        "clock": raw.get("clock") or "",
        "period": raw.get("period") or 0,
        "team": raw.get("teamTricode") or "",
        "player": raw.get("playerName") or raw.get("personName") or "",
        "score_home": _to_int(raw.get("scoreHome")),
        "score_away": _to_int(raw.get("scoreAway")),
        "shot_result": raw.get("shotResult") or "",
        "points": _points_from_play(raw),
        "raw": raw,
    }


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _points_from_play(raw):
    value = raw.get("value")
    if value not in (None, ""):
        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    action_type = (raw.get("actionType") or "").lower()
    shot_result = (raw.get("shotResult") or "").lower()
    description = (raw.get("description") or "").lower()
    made = shot_result == "made" or ("miss" not in description and "missed" not in description)

    if action_type == "3pt" and made:
        return 3
    if action_type == "2pt" and made:
        return 2
    if action_type == "freethrow" and made:
        return 1
    return 0
