from __future__ import annotations

from datetime import date, timedelta

import nba_client
from nba_api.stats.endpoints import scoreboardv3


def _team_codes_from_game_code(game_code):
    if not game_code or "/" not in game_code:
        return "", ""
    matchup = game_code.split("/", 1)[1]
    if len(matchup) < 6:
        return "", ""
    return matchup[:3], matchup[3:6]


def get_live_game_ids() -> list[str]:
    return nba_client.get_live_game_ids()


def _schedule_games_for_date(game_date):
    try:
        board = scoreboardv3.ScoreboardV3(game_date=game_date.isoformat(), league_id="00")
        df = board.game_header.get_data_frame()
    except Exception:
        return []

    if df.empty:
        return []

    games = []
    for row in df.to_dict("records"):
        game_id = row.get("gameId")
        game_code = row.get("gameCode")
        away_team, home_team = _team_codes_from_game_code(game_code)
        if not game_id:
            continue
        games.append({
            "gameId": game_id,
            "gameCode": game_code,
            "gameStatus": row.get("gameStatus"),
            "gameStatusText": row.get("gameStatusText"),
            "gameDate": game_date.isoformat(),
            "gameTime": row.get("gameEt") or row.get("gameTimeUTC"),
            "period": row.get("period") or 0,
            "gameClock": row.get("gameClock") or "",
            "gameLabel": row.get("gameLabel") or "",
            "gameSubLabel": row.get("gameSubLabel") or "",
            "seriesText": row.get("seriesText") or "",
            "homeTeam": {
                "teamTricode": home_team,
                "teamCity": "",
                "teamName": home_team,
                "score": "",
            },
            "awayTeam": {
                "teamTricode": away_team,
                "teamCity": "",
                "teamName": away_team,
                "score": "",
            },
        })
    return games


def get_upcoming_games(days_ahead=1):
    games = []
    today = date.today()
    for offset in range(days_ahead + 1):
        games.extend(_schedule_games_for_date(today + timedelta(days=offset)))
    return games


def get_watchlist(days_ahead=1):
    scheduled_games = get_upcoming_games(days_ahead=days_ahead)
    live_games = nba_client.get_games()
    live_by_id = {g.get("gameId"): g for g in live_games if g.get("gameId")}
    watchlist = []

    for game in scheduled_games:
        game_id = game.get("gameId")
        live_game = live_by_id.get(game_id)
        if live_game:
            game["gameStatus"] = live_game.get("gameStatus")
            game["gameStatusText"] = live_game.get("gameStatusText")
            game["period"] = live_game.get("period")
            game["gameClock"] = live_game.get("gameClock")
            game["homeTeam"] = live_game.get("homeTeam", game["homeTeam"])
            game["awayTeam"] = live_game.get("awayTeam", game["awayTeam"])
        watchlist.append(game)

    seen_ids = {game.get("gameId") for game in watchlist}
    for game in live_games:
        if game.get("gameId") and game.get("gameId") not in seen_ids:
            watchlist.append({
                "gameId": game.get("gameId"),
                "gameCode": game.get("gameCode"),
                "gameStatus": game.get("gameStatus"),
                "gameStatusText": game.get("gameStatusText"),
                "gameDate": None,
                "gameTime": game.get("gameEt") or game.get("gameTimeUTC"),
                "period": game.get("period"),
                "gameClock": game.get("gameClock"),
                "gameLabel": "",
                "gameSubLabel": "",
                "seriesText": "",
                "homeTeam": game.get("homeTeam", {}),
                "awayTeam": game.get("awayTeam", {}),
            })
    return watchlist


if __name__ == "__main__":
    for game in get_watchlist(days_ahead=1):
        print(game)