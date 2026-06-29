from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


DB_PATH = "plays.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plays (
                action_number INTEGER,
                game_id TEXT NOT NULL,
                period INTEGER,
                clock TEXT,
                player_name TEXT,
                team TEXT,
                action_type TEXT,
                description TEXT,
                score_home TEXT,
                score_away TEXT,
                inserted_at TEXT,
                PRIMARY KEY (game_id, action_number)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plays_game_id ON plays (game_id)")


def _normalize(play_dict):
    action_number = play_dict.get("actionNumber")
    return {
        "action_number": action_number,
        "game_id": play_dict.get("gameId"),
        "period": play_dict.get("period"),
        "clock": play_dict.get("clock"),
        "player_name": play_dict.get("personName") or play_dict.get("playerName"),
        "team": play_dict.get("teamTricode") or play_dict.get("team"),
        "action_type": play_dict.get("actionType"),
        "description": play_dict.get("description"),
        "score_home": play_dict.get("scoreHome"),
        "score_away": play_dict.get("scoreAway"),
        "inserted_at": datetime.now(timezone.utc).isoformat(),
    }


def save_play(play_dict):
    row = _normalize(play_dict)
    if row["action_number"] is None:
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO plays (
                    action_number, game_id, period, clock, player_name, team,
                    action_type, description, score_home, score_away, inserted_at
                ) VALUES (
                    :action_number, :game_id, :period, :clock, :player_name, :team,
                    :action_type, :description, :score_home, :score_away, :inserted_at
                )
                """,
                row,
            )
            print(f"Saved action {row['action_number']} for game {row['game_id']}")
    except Exception as e:
        print(f"DB ERROR saving action {row['action_number']}: {e}")

def get_seen_action_numbers(game_id):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT action_number FROM plays WHERE game_id = ?",
            (game_id,),
        ).fetchall()
    return {row[0] for row in rows}

