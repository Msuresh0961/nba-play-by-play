import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# Test scoreboard
r = requests.get("https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json", headers=HEADERS)
games = r.json().get("scoreboard", {}).get("games", [])
for g in games:
    print(g["gameId"], g["gameStatusText"], g["awayTeam"]["teamTricode"], "@", g["homeTeam"]["teamTricode"])

# Test play by play for first live game
live = [g for g in games if g["gameStatus"] == 2]
if live:
    game_id = live[0]["gameId"]
    r2 = requests.get(f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json", headers=HEADERS)
    actions = r2.json().get("game", {}).get("actions", [])
    print(f"\n{len(actions)} plays for game {game_id}")
    for a in actions[-3:]:
        print(a.get("description"))