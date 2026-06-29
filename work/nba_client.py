"""
Direct NBA CDN client.
For live games: hits cdn.nba.com live play-by-play endpoint.
For historical games: falls back to nba_api PlayByPlayV3.
"""
from __future__ import annotations
import requests

CDN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
CDN_PBP_URL    = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"


def get_scoreboard() -> dict:
    r = requests.get(SCOREBOARD_URL, headers=CDN_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def get_games() -> list[dict]:
    return get_scoreboard().get("scoreboard", {}).get("games", [])


def get_live_game_ids() -> list[str]:
    return [g["gameId"] for g in get_games() if g.get("gameStatus") == 2]


def _fetch_from_cdn(game_id: str) -> list[dict]:
    url = CDN_PBP_URL.format(game_id=game_id)
    r = requests.get(url, headers=CDN_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json().get("game", {}).get("actions", [])


def _fetch_from_nba_api(game_id: str) -> list[dict]:
    """
    Uses nba_api PlayByPlayV3 which works for all historical games.
    Returns actions in the same shape as the CDN endpoint.
    """
    from nba_api.stats.endpoints import playbyplayv3
    pbp = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=60)
    df  = pbp.get_data_frames()[0]

    if df.empty:
        return []

    actions = []
    for _, row in df.iterrows():
        actions.append({
            "actionNumber": row.get("actionNumber"),
            "actionType":   row.get("actionType"),
            "description":  row.get("description") or "",
            "clock":        row.get("clock") or "",
            "period":       row.get("period"),
            "playerName":   row.get("playerName") or row.get("playerNameI") or "",
            "teamTricode":  row.get("teamTricode") or "",
            "scoreHome":    row.get("scoreHome"),
            "scoreAway":    row.get("scoreAway"),
            "shotResult":   row.get("shotResult") or "",
            "qualifiers":   row.get("qualifiers") or [],
            "subType":      row.get("subType") or "",
        })

    return actions


def get_play_by_play(game_id: str) -> list[dict]:
    """
    Try CDN first (fast, works for live games).
    Fall back to nba_api PlayByPlayV3 for historical games.
    """
    try:
        actions = _fetch_from_cdn(game_id)
        if actions:
            print(f"[nba_client] CDN: {len(actions)} actions for {game_id}")
            return actions
        print(f"[nba_client] CDN empty for {game_id}, trying nba_api")
    except Exception as e:
        print(f"[nba_client] CDN failed ({e}), trying nba_api")

    try:
        actions = _fetch_from_nba_api(game_id)
        print(f"[nba_client] nba_api: {len(actions)} actions for {game_id}")
        return actions
    except Exception as e:
        print(f"[nba_client] nba_api also failed: {e}")
        return []