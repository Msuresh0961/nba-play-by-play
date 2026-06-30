# 🏀 NBA Live Alert System

A real-time NBA play-by-play alert system with voice narration, game analysis, and a live broadcast dashboard. Built with Python/Flask and vanilla JS.

---

## Features

- **Live play-by-play feed** — polls the NBA CDN every 5 seconds for new plays
- **Voice narration** — speaks plays aloud using Puter TTS with browser speech fallback
- **Push notifications** — browser alerts for big plays when the tab is in the background
- **Game analysis panel** — win probability, FG%, 3PT%, turnovers, last 5 min stats
- **Momentum graph** — canvas chart showing score differential over time
- **Quarter scores** — running score by quarter for both teams
- **Box score** — full per-player stats (PTS, FGM, FGA, FG%, 3PM, REB, AST, STL, BLK, TO)
- **Player filtering** — click any player chip to filter the feed to their plays only
- **Projected final score** — pace-based score projection
- **Game leader** — tracks highest-impact player with clutch point bonus
- **Game summary** — spoken and displayed final recap when game ends
- **Series info** — shows playoff series context (Game 5, tied 2-2, etc.)
- **Excitement score** — ranks live games by closeness, run momentum, and game time
- **Three themes** — Arena (dark), Broadcast (light), Neon

---

## Project Structure

```
├── app.py                  # Flask backend, polling threads, API routes
├── nba_client.py           # Direct NBA CDN client (replaces nba_api live endpoints)
├── game_finder.py          # Finds live and upcoming games
├── data_normalizer.py      # Cleans raw NBA API play data
├── game_state.py           # Tracks score, runs, lead changes in memory
├── event_processor.py      # Classifies plays (dunk, three pointer, lead change, etc.)
├── commentary.py           # Generates varied natural language commentary
├── database.py             # Saves all plays to SQLite (plays.db)
├── game_analysis.py        # Win probability, FG%, momentum, box score, projections
├── templates/
│   ├── index.html          # Live game cards with excitement scores and badges
│   └── game.html           # Two-column game dashboard
└── static/
    ├── css/styles.css       # Dark arena theme with broadcast and neon variants
    ├── js/game.js           # Live feed, analysis, box score, TTS, notifications
    └── js/theme.js          # Theme switcher
```

---

## Setup

### Requirements

- Python 3.10+
- pip

### Install

```bash
git clone https://github.com/Msuresh0961/nba-play-by-play.git
cd nba-live-alerts
pip install flask nba_api
```

### Run

```bash
python app.py
```

Then open [http://localhost:5000](http://localhost:5000).

---

## How It Works

### Backend

1. `game_finder.py` polls the NBA scoreboard for live and upcoming games
2. When a game goes live (status = 2), a background thread starts for it via `update_game_state`
3. Every 5 seconds, the thread fetches all play-by-play actions from the NBA CDN
4. New plays (not yet in the DB) are processed through the pipeline:
   - `data_normalizer.py` — maps raw NBA API fields to a clean internal format
   - `game_state.py` — updates running score, detects lead changes and scoring runs
   - `event_processor.py` — classifies the play type and priority
   - `commentary.py` — generates a natural spoken sentence
   - `database.py` — saves the raw action to SQLite with `game_id` + `action_number` as composite primary key
5. Events queue in memory and are returned to the frontend via `/api/game/<id>/feed`

### Frontend

- `game.js` polls `/feed` every 5s, `/analysis` and `/boxscore` every 15s, `/series` every 30s
- New events are prepended to the sidebar feed and spoken aloud via Puter TTS
- High-priority events (dunks, three pointers, lead changes, clutch scores, scoring runs) trigger browser push notifications when the tab is hidden
- Player chips are built from the box score — clicking one filters the feed to that player's plays

### Database

SQLite (`plays.db`) with a single `plays` table. Primary key is `(game_id, action_number)` so plays from different games never collide.

---

## API Routes

| Route | Description |
|---|---|
| `GET /` | Index page with live game cards |
| `GET /game/<game_id>` | Game dashboard |
| `GET /api/games` | All games with excitement scores |
| `GET /api/game/<id>/feed` | New events since last poll |
| `GET /api/game/<id>/analysis` | Win probability, stats, momentum, projections |
| `GET /api/game/<id>/boxscore` | Per-player box score |
| `GET /api/game/<id>/series` | Playoff series info |
| `POST /api/game/<id>/mock-play` | Inject a test play (dev only) |

---

## Testing with Historical Games

The NBA CDN keeps play-by-play for every completed game this season. To test against a finished game, find a game ID from a recent box score URL on NBA.com (e.g. `nba.com/game/0042400406`) and navigate directly to:

```
http://localhost:5000/game/0042400406
```

All plays will load immediately since the game is complete. The analysis, box score, and momentum graph will all populate from the saved plays.

---

## Known Limitations

- Win probability model is heuristic-based (score margin, FG%, recent scoring, runs) — not a trained model
- Play-by-play data from the NBA CDN can have a 30-60 second delay vs broadcast
- Puter TTS requires a Puter account for best quality; falls back to browser speech synthesis automatically

---

