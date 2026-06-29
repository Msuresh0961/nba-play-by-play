from __future__ import annotations

import threading
import time
from collections import deque

from flask import Flask, jsonify, render_template, request

import commentary
import data_normalizer
import database
import event_processor
import game_finder
import game_analysis
from game_state import GameState
import nba_client


app = Flask(__name__)
database.init_db()

game_state = {}
game_lock = threading.Lock()
running_threads = {}
watcher_started = False

# Replay config: seconds between each play (0 = instant, 0.5 = fast, 2 = dramatic)
REPLAY_DELAY = 0.4

TEAM_NAMES = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
    "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
    "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
    "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
    "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
    "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
    "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
    "UTA": "Jazz", "WAS": "Wizards",
}


@app.route("/api/game/<game_id>/analysis")
def api_game_analysis(game_id):
    with game_lock:
        state = game_state.get(game_id, _empty_runtime_state())
        engine = state["engine"]
        summary_data = state["summary"]

    home_team = summary_data.get("homeTeam", {})
    away_team = summary_data.get("awayTeam", {})

    snapshot = {
        "home_tricode": home_team.get("teamTricode") or engine.home_tricode or "HOME",
        "away_tricode": away_team.get("teamTricode") or engine.away_tricode or "AWAY",
        "score_home": engine.score_home,
        "score_away": engine.score_away,
        "period": engine.period,
        "clock": engine.clock,
        "current_run_team": engine.current_run_team,
        "current_run_points": engine.current_run_points,
    }

    result = game_analysis.analyze(game_id, snapshot)
    return jsonify(result)


def _serialize_game(game):
    if not game:
        return None
    return {
        "gameId": game.get("gameId"),
        "gameStatus": game.get("gameStatus"),
        "gameStatusText": game.get("gameStatusText"),
        "gameDate": game.get("gameDate"),
        "gameTime": game.get("gameTime"),
        "period": game.get("period"),
        "gameClock": game.get("gameClock"),
        "gameLabel": game.get("gameLabel"),
        "gameSubLabel": game.get("gameSubLabel"),
        "seriesText": game.get("seriesText"),
        "homeTeam": game.get("homeTeam", {}),
        "awayTeam": game.get("awayTeam", {}),
    }






def _empty_runtime_state(summary=None):
    return {
        "plays": deque(maxlen=200),
        "events": deque(maxlen=200),
        "summary": summary or {},
        "engine": GameState(),
        "last_error": None,
        "replay_mode": False,
        "replay_progress": 0,   # how many plays have been drip-fed so far
        "replay_total": 0,      # total plays in the historical game
    }


def _event_from_raw_action(raw_action, engine):
    normalized_play = data_normalizer.normalize_play(raw_action)
    state_snapshot = engine.update(normalized_play)
    event = event_processor.classify_event(normalized_play, state_snapshot)
    event["narration"] = commentary.generate_commentary(event, state_snapshot)
    return event


def fetch_actions(game_id):
    return nba_client.get_play_by_play(game_id)


def game_snapshot(game_id):
    games = nba_client.get_games()
    match = next((g for g in games if g.get("gameId") == game_id), None)
    if not match:
        return None
    return {
        "gameId": match.get("gameId"),
        "gameStatus": match.get("gameStatus"),
        "gameStatusText": match.get("gameStatusText"),
        "gameClock": match.get("gameClock"),
        "period": match.get("period"),
        "homeTeam": match.get("homeTeam", {}),
        "awayTeam": match.get("awayTeam", {}),
    }


def _build_historical_summary(actions, game_id, final=False):
    """
    Build a summary dict from play-by-play data for historical games.
    When final=False (default), hides the score so replay feels live.
    When final=True, reveals the actual final score.
    """
    if not actions:
        return {}

    # Extract tricodes — first two distinct non-empty tricodes
    seen = []
    for a in actions:
        tc = a.get("teamTricode")
        if tc and tc not in seen:
            seen.append(tc)
        if len(seen) == 2:
            break

    away_tricode = seen[0] if len(seen) > 0 else ""
    home_tricode = seen[1] if len(seen) > 1 else ""

    max_period = max((a.get("period") or 1 for a in actions), default=4)

    if final:
        # Reveal actual final score
        home_score, away_score = 0, 0
        for action in reversed(actions):
            sh = action.get("scoreHome")
            sa = action.get("scoreAway")
            if sh is not None and sa is not None:
                try:
                    home_score = int(sh)
                    away_score = int(sa)
                    break
                except (ValueError, TypeError):
                    pass
        status      = 3
        status_text = "Final"
        clock       = ""
    else:
        # Hide score at start of replay
        home_score  = 0
        away_score  = 0
        status      = 2  # appear live
        status_text = "In Progress"
        clock       = "PT12M00.00S"

    return {
        "gameId": game_id,
        "gameStatus": status,
        "gameStatusText": status_text,
        "gameClock": clock,
        "period": 1 if not final else max_period,
        "homeTeam": {
            "teamTricode": home_tricode,
            "teamCity": "",
            "teamName": TEAM_NAMES.get(home_tricode, home_tricode),
            "score": home_score,
        },
        "awayTeam": {
            "teamTricode": away_tricode,
            "teamCity": "",
            "teamName": TEAM_NAMES.get(away_tricode, away_tricode),
            "score": away_score,
        },
    }


def update_game_state(game_id):
    """Worker for LIVE games — polls NBA CDN every 5 seconds."""
    while True:
        try:
            actions = fetch_actions(game_id)
            seen = database.get_seen_action_numbers(game_id)

            with game_lock:
                state = game_state.setdefault(game_id, _empty_runtime_state())
                engine = state["engine"]

            new_events = []
            for action in actions:
                action_number = action.get("actionNumber")
                if action_number in seen:
                    continue
                action["gameId"] = game_id
                event = _event_from_raw_action(action, engine)
                database.save_play(action)
                seen.add(action_number)
                new_events.append(event)

            snapshot = game_snapshot(game_id)

            with game_lock:
                state = game_state.setdefault(game_id, _empty_runtime_state(snapshot or {}))
                if snapshot:
                    state["summary"] = snapshot
                    engine = state["engine"]
                    if not engine.home_tricode:
                        engine.home_tricode = snapshot.get("homeTeam", {}).get("teamTricode")
                    if not engine.away_tricode:
                        engine.away_tricode = snapshot.get("awayTeam", {}).get("teamTricode")
                for event in new_events:
                    state["events"].append(event)
                    state["plays"].append(event["play"])
                state["last_error"] = None
            time.sleep(5)
        except Exception as exc:
            with game_lock:
                state = game_state.setdefault(game_id, _empty_runtime_state())
                state["last_error"] = str(exc)
            time.sleep(10)


def update_game_state_replay(game_id, delay=REPLAY_DELAY):
    """
    Worker for HISTORICAL games.
    Fetches all plays once, then drip-feeds them one at a time with `delay`
    seconds between each so the feed feels live. After all plays are fed,
    the thread sleeps — no more polling needed.
    """
    try:
        print(f"[REPLAY] Starting replay for {game_id} at {delay}s/play")
        all_actions = fetch_actions(game_id)
        if not all_actions:
            print(f"[REPLAY] No actions found for {game_id}")
            return

        # Sort by action number to ensure correct order
        all_actions = sorted(all_actions, key=lambda a: a.get("actionNumber") or 0)


        # Start with score-hidden summary so replay feels live
        initial_summary = _build_historical_summary(all_actions, game_id, final=False)
        final_summary   = _build_historical_summary(all_actions, game_id, final=True)

        seen = database.get_seen_action_numbers(game_id)

        with game_lock:
            state = game_state.setdefault(game_id, _empty_runtime_state(initial_summary))
            state["summary"] = initial_summary
            state["replay_mode"] = True
            state["replay_total"] = len(all_actions)
            engine = state["engine"]
            if initial_summary.get("homeTeam"):
                engine.home_tricode = initial_summary["homeTeam"].get("teamTricode")
                engine.away_tricode = initial_summary["awayTeam"].get("teamTricode")

        print(f"[REPLAY] {len(all_actions)} total actions, {len(seen)} already seen")

        for action in all_actions:
            action_number = action.get("actionNumber")
            if action_number in seen:
                with game_lock:
                    state = game_state.get(game_id, _empty_runtime_state())
                    engine = state["engine"]
                action["gameId"] = game_id
                normalized_play = data_normalizer.normalize_play(action)
                engine.update(normalized_play)
                with game_lock:
                    state["replay_progress"] = (state.get("replay_progress") or 0) + 1
                continue

            action["gameId"] = game_id
            with game_lock:
                state = game_state.get(game_id, _empty_runtime_state())
                engine = state["engine"]

            event = _event_from_raw_action(action, engine)
            database.save_play(action)
            seen.add(action_number)

            sh = action.get("scoreHome")
            sa = action.get("scoreAway")

            with game_lock:
                state = game_state.get(game_id, _empty_runtime_state())
                state["events"].append(event)
                state["plays"].append(event["play"])
                state["replay_progress"] = (state.get("replay_progress") or 0) + 1
                state["last_error"] = None
                if sh is not None and sa is not None:
                    try:
                        state["summary"]["homeTeam"]["score"] = int(sh)
                        state["summary"]["awayTeam"]["score"] = int(sa)
                        state["summary"]["period"] = action.get("period") or state["summary"].get("period", 1)
                        state["summary"]["gameClock"] = action.get("clock") or ""
                    except (ValueError, TypeError, KeyError):
                        pass

            if delay > 0:
                time.sleep(delay)

        print(f"[REPLAY] Finished replaying {game_id}")

        with game_lock:
            state = game_state.get(game_id, _empty_runtime_state())
            state["summary"] = final_summary


    except Exception as exc:
        print(f"[REPLAY] Error: {exc}")
        with game_lock:
            state = game_state.setdefault(game_id, _empty_runtime_state())
            state["last_error"] = str(exc)


def _is_historical_game(game_id):
    """
    Returns True if the game is not currently live (historical or future).
    Checks the live scoreboard; if game_id not found there, treat as historical.
    """
    try:
        games = nba_client.get_games()
        for g in games:
            if g.get("gameId") == game_id:
                return g.get("gameStatus") != 2  # 2 = live
        return True  # not on scoreboard = historical
    except Exception:
        return True  # if API fails, assume historical and replay


@app.route("/api/game/<game_id>/replay-status")
def api_replay_status(game_id):
    with game_lock:
        state = game_state.get(game_id, _empty_runtime_state())
    return jsonify({
        "replay_mode": state.get("replay_mode", False),
        "replay_progress": state.get("replay_progress", 0),
        "replay_total": state.get("replay_total", 0),
    })


@app.route("/api/game/<game_id>/boxscore")
def api_box_score(game_id):
    result = game_analysis.box_score(game_id)
    return jsonify(result)


@app.route("/api/game/<game_id>/series")
def api_series(game_id):
    with game_lock:
        state = game_state.get(game_id, _empty_runtime_state())
        summary = state.get("summary", {})
    return jsonify({
        "gameLabel": summary.get("gameLabel") or "",
        "gameSubLabel": summary.get("gameSubLabel") or "",
        "seriesText": summary.get("seriesText") or "",
        "gameStatusText": summary.get("gameStatusText") or "",
        "period": summary.get("period") or 0,
        "gameClock": summary.get("gameClock") or "",
    })


def ensure_worker(game_id):
    if game_id in running_threads:
        return
    if _is_historical_game(game_id):
        print(f"[WORKER] {game_id} is historical — starting replay worker")
        target = lambda: update_game_state_replay(game_id, delay=REPLAY_DELAY)
    else:
        print(f"[WORKER] {game_id} is live — starting live worker")
        target = lambda: update_game_state(game_id)

    thread = threading.Thread(target=target, daemon=True)
    running_threads[game_id] = thread
    thread.start()


def start_watchlist_watcher():
    global watcher_started
    if watcher_started:
        return

    def watch():
        while True:
            try:
                watchlist = game_finder.get_watchlist(days_ahead=1)
                with game_lock:
                    for game in watchlist:
                        game_id = game.get("gameId")
                        if not game_id:
                            continue
                        state = game_state.setdefault(game_id, _empty_runtime_state(_serialize_game(game) or {}))
                        state["summary"] = _serialize_game(game) or state["summary"]
                        if game.get("gameStatus") == 2:
                            ensure_worker(game_id)
                time.sleep(60)
            except Exception:
                time.sleep(60)

    watcher_started = True
    threading.Thread(target=watch, daemon=True).start()


@app.route("/")
def index():
    start_watchlist_watcher()
    watchlist = []
    try:
        watchlist = game_finder.get_watchlist(days_ahead=1)
    except Exception:
        watchlist = []
    games = []
    for game in watchlist:
        game_id = game.get("gameId")
        if not game_id:
            continue
        games.append(game)
        if game.get("gameStatus") == 2:
            ensure_worker(game_id)
    return render_template("index.html", games=games)


@app.route("/game/<game_id>")
def game_view(game_id):
    start_watchlist_watcher()
    ensure_worker(game_id)
    return render_template("game.html", game_id=game_id)


@app.route("/api/games")
def api_games():
    try:
        start_watchlist_watcher()
        watchlist = game_finder.get_watchlist(days_ahead=1)
        payload = []
        for game in watchlist:
            game_id = game.get("gameId")
            if game.get("gameStatus") == 2:
                ensure_worker(game_id)

            exc = 0
            if game.get("gameStatus") == 2 and game_id:
                with game_lock:
                    state = game_state.get(game_id)
                if state:
                    engine = state["engine"]
                    from game_analysis import excitement_score, _clock_to_seconds
                    exc = excitement_score(
                        engine.score_home,
                        engine.score_away,
                        engine.period or 1,
                        _clock_to_seconds(engine.clock or "PT12M00.00S"),
                        engine.current_run_points,
                    )

            game["excitement_score"] = exc
            payload.append(game)

        payload.sort(key=lambda g: (g.get("gameStatus") == 2, g.get("excitement_score", 0)), reverse=True)
        return jsonify({"games": payload})
    except Exception as exc:
        return jsonify({"games": [], "error": str(exc)}), 500


@app.route("/api/game/<game_id>/feed")
def api_game_feed(game_id):
    start_watchlist_watcher()
    ensure_worker(game_id)
    with game_lock:
        state = game_state.get(game_id, _empty_runtime_state())
        events = list(state.get("events", []))
        state.get("events", deque()).clear()
        state["plays"].clear()
        summary = state["summary"]
        last_error = state["last_error"]
        replay_mode = state.get("replay_mode", False)
        replay_progress = state.get("replay_progress", 0)
        replay_total = state.get("replay_total", 0)
    return jsonify({
        "gameId": game_id,
        "summary": summary,
        "events": events,
        "plays": [e["play"] for e in events],
        "last_error": last_error,
        "replay_mode": replay_mode,
        "replay_progress": replay_progress,
        "replay_total": replay_total,
    })




@app.route("/api/game/<game_id>/mock-play", methods=["POST"])
def api_mock_play(game_id):
    with game_lock:
        state = game_state.setdefault(game_id, _empty_runtime_state())
        engine = state["engine"]
        current_away = (engine.score_away or 0) + 3
        current_home = engine.score_home or 0

    raw_action = {
        "gameId": game_id,
        "actionNumber": int(time.time() * 1000),
        "actionType": "3pt",
        "description": "J. Brunson 26' 3PT Jump Shot (3 PTS)",
        "clock": "PT11M22.00S",
        "period": 1,
        "playerName": "J. Brunson",
        "teamTricode": "NYK",
        "scoreHome": str(current_home),
        "scoreAway": str(current_away),
        "shotResult": "Made",
        "value": "3",
    }

    database.save_play(raw_action)

    with game_lock:
        state = game_state.setdefault(game_id, _empty_runtime_state())
        event = _event_from_raw_action(raw_action, state["engine"])
        state["events"].append(event)
        state["plays"].append(event["play"])

    return jsonify({"ok": True, "event": event})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)