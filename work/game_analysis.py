from __future__ import annotations

import sqlite3
import re
from database import DB_PATH


def _clock_to_seconds(clock: str) -> float:
    """Convert NBA clock string 'PT11M22.00S' to total seconds remaining."""
    if not clock:
        return 0
    m = re.search(r"PT(\d+)M([\d.]+)S", clock)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return 0


def _fetch_plays(game_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM plays
            WHERE game_id = ?
            ORDER BY action_number ASC
            """,
            (game_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _is_made_shot(play: dict) -> bool:
    action_type = (play.get("action_type") or "").lower()
    description = (play.get("description") or "").lower()
    if action_type not in ("2pt", "3pt", "freethrow"):
        return False
    return "miss" not in description


def _is_shot_attempt(play: dict) -> bool:
    action_type = (play.get("action_type") or "").lower()
    return action_type in ("2pt", "3pt", "freethrow")


def _points_from_play(play: dict) -> int:
    action_type = (play.get("action_type") or "").lower()
    description = (play.get("description") or "").lower()
    if "miss" in description:
        return 0
    if action_type == "3pt":
        return 3
    if action_type == "2pt":
        return 2
    if action_type == "freethrow":
        return 1
    return 0


def _recent_plays(plays: list[dict], current_period: int, current_clock: str, window_seconds: float = 300) -> list[dict]:
    """Return plays from the last `window_seconds` seconds of game time."""
    current_secs = _clock_to_seconds(current_clock)

    # Convert current position to absolute game seconds elapsed
    # Each quarter is 12 min = 720 sec; OT is 5 min = 300 sec
    def abs_elapsed(period, clock_secs):
        quarter_len = 720 if period <= 4 else 300
        quarters_done = (min(period, 4) - 1) * 720
        ot_done = max(0, period - 4 - 1) * 300 if period > 5 else 0
        return quarters_done + ot_done + (quarter_len - clock_secs)

    current_elapsed = abs_elapsed(current_period, current_secs)
    cutoff = current_elapsed - window_seconds

    result = []
    for p in plays:
        p_elapsed = abs_elapsed(p.get("period") or 1, _clock_to_seconds(p.get("clock") or ""))
        if p_elapsed >= cutoff:
            result.append(p)
    return result


def _team_stats(plays: list[dict], team: str) -> dict:
    team_plays = [p for p in plays if (p.get("team") or "").upper() == team.upper()]
    attempts = [p for p in team_plays if _is_shot_attempt(p)]
    made = [p for p in attempts if _is_made_shot(p)]

    attempts_2pt = [p for p in attempts if (p.get("action_type") or "").lower() == "2pt"]
    made_2pt = [p for p in attempts_2pt if _is_made_shot(p)]
    attempts_3pt = [p for p in attempts if (p.get("action_type") or "").lower() == "3pt"]
    made_3pt = [p for p in attempts_3pt if _is_made_shot(p)]
    attempts_ft = [p for p in attempts if (p.get("action_type") or "").lower() == "freethrow"]
    made_ft = [p for p in attempts_ft if _is_made_shot(p)]

    turnovers = len([p for p in team_plays if (p.get("action_type") or "").lower() == "turnover"])
    points = sum(_points_from_play(p) for p in team_plays)

    def pct(m, a):
        return round(len(m) / len(a) * 100, 1) if a else None

    return {
        "points": points,
        "fg_pct": pct(made, attempts),
        "two_pt_pct": pct(made_2pt, attempts_2pt),
        "three_pt_pct": pct(made_3pt, attempts_3pt),
        "ft_pct": pct(made_ft, attempts_ft),
        "fg_attempts": len(attempts),
        "fg_made": len(made),
        "three_attempts": len(attempts_3pt),
        "three_made": len(made_3pt),
        "turnovers": turnovers,
    }


def _quarter_scores(plays: list[dict], team: str) -> dict[int, int]:
    quarters: dict[int, int] = {}
    for p in plays:
        if (p.get("team") or "").upper() != team.upper():
            continue
        period = p.get("period") or 0
        quarters[period] = quarters.get(period, 0) + _points_from_play(p)
    return quarters


def _win_probability(
    home_score: int,
    away_score: int,
    home_stats: dict,
    away_stats: dict,
    home_recent: dict,
    away_recent: dict,
    current_run_team: str | None,
    current_run_points: int,
    home_tricode: str,
    away_tricode: str,
    period: int,
    clock_secs: float,
) -> tuple[float, float]:
    """
    Returns (home_win_prob, away_win_prob) as percentages.
    Based entirely on in-game factors.
    """
    score_diff = home_score - away_score  # positive = home leading

    # --- Factor 1: Score margin (most important, weighted by time remaining) ---
    total_game_secs = 4 * 720
    elapsed = min((period - 1) * 720 + (720 - clock_secs), total_game_secs)
    time_weight = elapsed / total_game_secs  # 0 at tip, 1 at final buzzer
    score_factor = score_diff * (0.5 + time_weight * 1.5)  # grows as game ends

    # --- Factor 2: FG% differential (whole game) ---
    home_fg = home_stats.get("fg_pct") or 45.0
    away_fg = away_stats.get("fg_pct") or 45.0
    fg_factor = (home_fg - away_fg) * 0.3

    # --- Factor 3: 3PT% differential ---
    home_3pt = home_stats.get("three_pt_pct") or 35.0
    away_3pt = away_stats.get("three_pt_pct") or 35.0
    three_factor = (home_3pt - away_3pt) * 0.15

    # --- Factor 4: Recent scoring (last 5 min) ---
    home_recent_pts = home_recent.get("points", 0)
    away_recent_pts = away_recent.get("points", 0)
    recent_factor = (home_recent_pts - away_recent_pts) * 0.4

    # --- Factor 5: Current run ---
    run_factor = 0.0
    if current_run_team and current_run_points >= 6:
        if current_run_team.upper() == home_tricode.upper():
            run_factor = current_run_points * 0.3
        else:
            run_factor = -current_run_points * 0.3

    # --- Factor 6: Turnover differential ---
    home_to = home_stats.get("turnovers", 0)
    away_to = away_stats.get("turnovers", 0)
    to_factor = (away_to - home_to) * 0.5

    total = score_factor + fg_factor + three_factor + recent_factor + run_factor + to_factor

    # Convert to probability using a sigmoid-like curve
    import math
    home_prob = 1 / (1 + math.exp(-total * 0.08))
    away_prob = 1 - home_prob

    return round(home_prob * 100, 1), round(away_prob * 100, 1)


def _summary_sentence(
    home_tricode: str,
    away_tricode: str,
    home_score: int,
    away_score: int,
    home_prob: float,
    away_prob: float,
    home_recent: dict,
    away_recent: dict,
    current_run_team: str | None,
    current_run_points: int,
    home_fg: float | None,
    away_fg: float | None,
) -> str:
    leading_team = home_tricode if home_score >= away_score else away_tricode
    margin = abs(home_score - away_score)
    leading_prob = home_prob if home_score >= away_score else away_prob

    parts = []

    if margin == 0:
        parts.append("Game is tied.")
    else:
        parts.append(f"{leading_team} lead by {margin} with a {leading_prob:.0f}% win probability.")

    home_r = home_recent.get("points", 0)
    away_r = away_recent.get("points", 0)
    if abs(home_r - away_r) >= 6:
        better = home_tricode if home_r > away_r else away_tricode
        parts.append(f"{better} have outscored their opponent {max(home_r, away_r)}-{min(home_r, away_r)} in the last 5 minutes.")

    if current_run_team and current_run_points >= 8:
        parts.append(f"{current_run_team} are on a {current_run_points}-0 run.")

    if home_fg is not None and away_fg is not None and abs(home_fg - away_fg) >= 8:
        better = home_tricode if home_fg > away_fg else away_tricode
        worse = away_tricode if home_fg > away_fg else home_tricode
        better_pct = max(home_fg, away_fg)
        worse_pct = min(home_fg, away_fg)
        parts.append(f"{better} shooting {better_pct}% vs {worse}'s {worse_pct}%.")

    return " ".join(parts)


def _momentum_graph(plays: list[dict], home_tricode: str, away_tricode: str, sample_every: int = 5) -> list[dict]:
    """
    Returns a list of {play_num, diff, home_score, away_score} points.
    diff = home_score - away_score (positive = home leading).
    Sampled every `sample_every` plays to keep the payload small.
    """
    points = []
    home_running = 0
    away_running = 0

    for i, play in enumerate(plays):
        pts = _points_from_play(play)
        team = (play.get("team") or "").upper()
        if team == home_tricode.upper():
            home_running += pts
        elif team == away_tricode.upper():
            away_running += pts

        # Use score fields from the play if available for accuracy
        sh = play.get("score_home")
        sa = play.get("score_away")
        try:
            h = int(sh) if sh not in (None, "") else home_running
            a = int(sa) if sa not in (None, "") else away_running
        except (ValueError, TypeError):
            h, a = home_running, away_running

        if i % sample_every == 0 or i == len(plays) - 1:
            points.append({
                "play_num": i + 1,
                "diff": h - a,
                "home_score": h,
                "away_score": a,
                "period": play.get("period") or 1,
            })

    return points


def _projected_score(
    home_score: int,
    away_score: int,
    period: int,
    clock_secs: float,
) -> dict:
    """Project final score based on current scoring pace."""
    total_game_secs = 4 * 720
    elapsed = max(1, (period - 1) * 720 + (720 - clock_secs))
    remaining = max(0, total_game_secs - elapsed)

    home_pace = home_score / elapsed * total_game_secs
    away_pace = away_score / elapsed * total_game_secs

    home_proj = round(home_score + (home_score / elapsed * remaining))
    away_proj = round(away_score + (away_score / elapsed * remaining))

    return {
        "home": home_proj,
        "away": away_proj,
        "home_pace": round(home_pace),
        "away_pace": round(away_pace),
    }


def _best_player(plays: list[dict]) -> dict | None:
    """Find the player with the most impact: points + clutch play bonus."""
    player_points: dict[str, int] = {}
    player_team: dict[str, str] = {}
    player_clutch: dict[str, int] = {}

    for play in plays:
        player = play.get("player_name") or ""
        if not player:
            continue
        pts = _points_from_play(play)
        team = play.get("team") or ""
        period = play.get("period") or 0
        clock = play.get("clock") or ""
        is_clutch = period >= 4 and clock.startswith("PT0")

        player_points[player] = player_points.get(player, 0) + pts
        player_team[player] = team
        if is_clutch and pts > 0:
            player_clutch[player] = player_clutch.get(player, 0) + pts

    if not player_points:
        return None

    # Score = points + 1.5x clutch points
    def impact(p):
        return player_points[p] + player_clutch.get(p, 0) * 0.5

    best = max(player_points.keys(), key=impact)
    return {
        "name": best,
        "team": player_team.get(best, ""),
        "points": player_points[best],
        "clutch_points": player_clutch.get(best, 0),
        "impact_score": round(impact(best), 1),
    }


def excitement_score(
    home_score: int,
    away_score: int,
    period: int,
    clock_secs: float,
    current_run_points: int,
) -> int:
    """
    Returns 0-100 score representing how exciting a game is right now.
    Used on the index page to surface the best game to watch.
    """
    import math

    score = 0

    # Close margin is exciting — peaks at 0, drops off as lead grows
    margin = abs(home_score - away_score)
    margin_score = max(0, 40 - margin * 2)
    score += margin_score

    # Late game is more exciting
    total_secs = 4 * 720
    elapsed = min((period - 1) * 720 + (720 - clock_secs), total_secs)
    time_factor = elapsed / total_secs  # 0 to 1
    score += time_factor * 30

    # Active run adds excitement
    if current_run_points >= 6:
        score += min(current_run_points * 1.5, 20)

    # Overtime
    if period > 4:
        score += 15

    return min(100, round(score))


def box_score(game_id: str) -> dict:
    """Returns per-player box score stats from saved plays."""
    plays = _fetch_plays(game_id)
    if not plays:
        return {"available": False, "teams": {}}

    players: dict[str, dict] = {}

    for play in plays:
        player = play.get("player_name") or ""
        team = play.get("team") or ""
        if not player or not team:
            continue

        key = f"{team}:{player}"
        if key not in players:
            players[key] = {
                "name": player, "team": team,
                "pts": 0, "fgm": 0, "fga": 0,
                "tpm": 0, "tpa": 0, "ftm": 0, "fta": 0,
                "reb": 0, "ast": 0, "stl": 0, "blk": 0, "to": 0,
            }

        p = players[key]
        action = (play.get("action_type") or "").lower()
        desc = (play.get("description") or "").lower()
        made = "miss" not in desc

        if action == "2pt":
            p["fga"] += 1
            if made:
                p["fgm"] += 1
                p["pts"] += 2
        elif action == "3pt":
            p["fga"] += 1
            p["tpa"] += 1
            if made:
                p["fgm"] += 1
                p["tpm"] += 1
                p["pts"] += 3
        elif action == "freethrow":
            p["fta"] += 1
            if made:
                p["ftm"] += 1
                p["pts"] += 1
        elif action == "rebound":
            p["reb"] += 1
        elif action == "assist":
            p["ast"] += 1
        elif action == "steal":
            p["stl"] += 1
        elif action == "block":
            p["blk"] += 1
        elif action == "turnover" and player:
            p["to"] += 1

    teams: dict[str, list] = {}
    for entry in players.values():
        t = entry["team"]
        if t not in teams:
            teams[t] = []
        fg_pct = round(entry["fgm"] / entry["fga"] * 100, 1) if entry["fga"] else 0.0
        tp_pct = round(entry["tpm"] / entry["tpa"] * 100, 1) if entry["tpa"] else 0.0
        ft_pct = round(entry["ftm"] / entry["fta"] * 100, 1) if entry["fta"] else 0.0
        teams[t].append({**entry, "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct})

    for t in teams:
        teams[t].sort(key=lambda x: x["pts"], reverse=True)

    return {"available": True, "teams": teams}


def analyze(game_id: str, state_snapshot: dict) -> dict:
    """
    Main entry point. Returns a full analysis dict ready to be JSON-serialized.
    """
    plays = _fetch_plays(game_id)
    if not plays:
        return {"available": False}

    home_tricode = state_snapshot.get("home_tricode", "HOME")
    away_tricode = state_snapshot.get("away_tricode", "AWAY")
    home_score = state_snapshot.get("score_home") or 0
    away_score = state_snapshot.get("score_away") or 0
    period = state_snapshot.get("period") or 1
    clock = state_snapshot.get("clock") or "PT12M00.00S"
    current_run_team = state_snapshot.get("current_run_team")
    current_run_points = state_snapshot.get("current_run_points", 0)

    clock_secs = _clock_to_seconds(clock)

    home_stats = _team_stats(plays, home_tricode)
    away_stats = _team_stats(plays, away_tricode)

    recent_plays = _recent_plays(plays, period, clock, window_seconds=300)
    home_recent = _team_stats(recent_plays, home_tricode)
    away_recent = _team_stats(recent_plays, away_tricode)

    home_quarters = _quarter_scores(plays, home_tricode)
    away_quarters = _quarter_scores(plays, away_tricode)

    home_prob, away_prob = _win_probability(
        home_score, away_score,
        home_stats, away_stats,
        home_recent, away_recent,
        current_run_team, current_run_points,
        home_tricode, away_tricode,
        period, clock_secs,
    )

    summary = _summary_sentence(
        home_tricode, away_tricode,
        home_score, away_score,
        home_prob, away_prob,
        home_recent, away_recent,
        current_run_team, current_run_points,
        home_stats.get("fg_pct"), away_stats.get("fg_pct"),
    )

    momentum = _momentum_graph(plays, home_tricode, away_tricode)
    projected = _projected_score(home_score, away_score, period, clock_secs)
    best_player = _best_player(plays)
    exc_score = excitement_score(home_score, away_score, period, clock_secs, current_run_points)

    return {
        "available": True,
        "home": {
            "tricode": home_tricode,
            "score": home_score,
            "win_prob": home_prob,
            "game": home_stats,
            "last_5_min": home_recent,
            "by_quarter": home_quarters,
        },
        "away": {
            "tricode": away_tricode,
            "score": away_score,
            "win_prob": away_prob,
            "game": away_stats,
            "last_5_min": away_recent,
            "by_quarter": away_quarters,
        },
        "current_run": {
            "team": current_run_team,
            "points": current_run_points,
        },
        "summary": summary,
        "period": period,
        "clock": clock,
        "momentum": momentum,
        "projected": projected,
        "best_player": best_player,
        "excitement_score": exc_score,
    }