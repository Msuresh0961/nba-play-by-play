from __future__ import annotations

import re
import random


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


def humanize_for_speech(text):
    text = re.sub(r"\b3PT\b", "three pointer", text, flags=re.IGNORECASE)
    text = re.sub(r"\b2PT\b", "two pointer", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPTS\b", "points", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPT\b", "points", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAST\b", "assist", text, flags=re.IGNORECASE)
    text = re.sub(r"\bREB\b", "rebound", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOREB\b", "offensive rebound", text, flags=re.IGNORECASE)
    text = re.sub(r"\bDREB\b", "defensive rebound", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSTL\b", "steal", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBLK\b", "block", text, flags=re.IGNORECASE)
    text = re.sub(r"\bTO\b", "turnover", text, flags=re.IGNORECASE)
    text = re.sub(r"\bFT\b", "free throw", text, flags=re.IGNORECASE)
    text = re.sub(r"\bQ1\b", "first quarter", text, flags=re.IGNORECASE)
    text = re.sub(r"\bQ2\b", "second quarter", text, flags=re.IGNORECASE)
    text = re.sub(r"\bQ3\b", "third quarter", text, flags=re.IGNORECASE)
    text = re.sub(r"\bQ4\b", "fourth quarter", text, flags=re.IGNORECASE)
    for abbr, name in TEAM_NAMES.items():
        text = re.sub(rf"\b{abbr}\b", name, text)
    return text


def _team(tricode):
    return TEAM_NAMES.get(tricode, tricode)


def _score_line(state):
    return f"{state['score_away']} to {state['score_home']}"


def generate_commentary(event, state):
    play = event["play"]
    player = play.get("player") or ""
    tricode = play.get("team", "")
    team = _team(tricode)
    etype = event["type"]

    # ── Three pointers ──────────────────────────────────────────
    if etype == "three_pointer":
        lines = [
            f"{player} drains a three for the {team}. {_score_line(state)}.",
            f"Bang! {player} from deep. The {team} lead {_score_line(state)}.",
            f"{player} with the three pointer. {team} crowd going wild.",
            f"From way downtown — {player}! Score now {_score_line(state)}.",
            f"{player} steps back and buries the three for {team}.",
            f"Cold-blooded from three. {player} with the bucket for {team}.",
        ]
        return random.choice(lines)

    # ── Dunks ────────────────────────────────────────────────────
    if etype == "dunk":
        lines = [
            f"{player} throws it down for the {team}!",
            f"Hammered home by {player}! {team} with authority.",
            f"Poster dunk by {player}! The {team} are rolling.",
            f"{player} with the slam! {team} electrifying the crowd.",
            f"Oh! {player} absolutely flushes it for {team}.",
        ]
        return random.choice(lines)

    # ── Lead changes ─────────────────────────────────────────────
    if etype == "lead_change":
        margin = abs(state["score_home"] - state["score_away"])
        lines = [
            f"Lead change! The {team} take it {_score_line(state)}.",
            f"The {team} flip the script. They lead by {margin}.",
            f"And just like that, {team} are in front. {_score_line(state)}.",
            f"Momentum shift — the {team} have the lead now.",
            f"{team} take the lead! Score is {_score_line(state)}.",
        ]
        return random.choice(lines)

    # ── Scoring runs ─────────────────────────────────────────────
    if etype == "scoring_run":
        run = state.get("current_run_points", 0)
        lines = [
            f"The {team} are on a {run}-nothing run. Huge momentum shift.",
            f"{run} unanswered for the {team}. The other team needs a timeout.",
            f"Can anyone stop the {team}? That's {run} straight points.",
            f"The {team} have caught fire. {run} points in a row.",
            f"Domination from the {team} — a {run} point run and counting.",
        ]
        return random.choice(lines)

    # ── Clutch scores ─────────────────────────────────────────────
    if etype == "clutch_score":
        lines = [
            f"Clutch basket from {player} when it matters most.",
            f"{player} steps up huge late in the game for {team}.",
            f"Ice in his veins. {player} with the big bucket for {team}.",
            f"When the pressure is on, {player} delivers for {team}.",
            f"That's a statement play. {player} — money in the clutch.",
        ]
        return random.choice(lines)

    # ── Made twos ────────────────────────────────────────────────
    if etype == "made_two":
        lines = [
            f"{player} scores for the {team}.",
            f"{player} with the bucket. {team} getting it done.",
            f"Good look for {player}. {team} on the board.",
            f"{player} converts for {team}. Score is {_score_line(state)}.",
            f"Easy two for {player} and the {team}.",
        ]
        return random.choice(lines)

    # ── Other play types ─────────────────────────────────────────
    ptype = play.get("type", "")

    if ptype == "turnover":
        lines = [
            f"Turnover by {player}. {_team(tricode)} gives it away.",
            f"{player} loses it. Turnover for {team}.",
            f"Costly turnover from {player}.",
        ]
        return random.choice(lines)

    if ptype == "foul":
        lines = [
            f"Foul called on {player}.",
            f"{player} gets whistled. Foul on the {team}.",
            f"The referee stops play. Foul on {player}.",
        ]
        return random.choice(lines)

    if ptype == "block":
        lines = [
            f"Blocked! {player} swats it away.",
            f"Get that out of here! {player} with the rejection.",
            f"{player} with the block. Huge defensive play for {team}.",
        ]
        return random.choice(lines)

    if ptype == "steal":
        lines = [
            f"{player} picks the pocket. Steal for {team}.",
            f"Hands in the passing lane — {player} with the steal.",
            f"Turnover forced by {player}. {team} on the break.",
        ]
        return random.choice(lines)

    if ptype == "timeout":
        return random.choice([
            "Timeout on the floor.",
            "The coach calls a timeout. Time to regroup.",
            "Play stops. Timeout called.",
        ])

    return humanize_for_speech(play.get("description") or "Play recorded.")


def generate_game_summary(home_tricode, away_tricode, home_score, away_score, best_player, home_stats, away_stats):
    """
    Called when game status = 3 (final). Returns a spoken summary sentence.
    """
    home = _team(home_tricode)
    away = _team(away_tricode)
    margin = abs(home_score - away_score)

    if home_score > away_score:
        winner, loser = home, away
        w_score, l_score = home_score, away_score
    else:
        winner, loser = away, home
        w_score, l_score = away_score, home_score

    # Descriptor based on margin
    if margin <= 3:
        descriptor = "in a nail-biter"
    elif margin <= 8:
        descriptor = "in a close one"
    elif margin <= 15:
        descriptor = "with a comfortable lead"
    else:
        descriptor = "in a dominant performance"

    intro_options = [
        f"Final score: {winner} {w_score}, {loser} {l_score}. {winner} win {descriptor}.",
        f"And that's the ballgame. {winner} defeat {loser} {w_score} to {l_score} {descriptor}.",
        f"{winner} take it {w_score} to {l_score} {descriptor}. {loser} fall tonight.",
    ]
    summary = random.choice(intro_options)

    # Best player callout
    if best_player and best_player.get("points", 0) > 0:
        bp_name = best_player["name"]
        bp_pts = best_player["points"]
        bp_team = _team(best_player.get("team", ""))
        player_lines = [
            f" {bp_name} led the way with {bp_pts} points for {bp_team}.",
            f" The game leader was {bp_name} with {bp_pts} for {bp_team}.",
            f" {bp_name} paced {bp_team} with {bp_pts} points.",
        ]
        summary += random.choice(player_lines)

    # Shooting efficiency note
    h_fg = home_stats.get("fg_pct")
    a_fg = away_stats.get("fg_pct")
    if h_fg and a_fg:
        better_team = home if h_fg > a_fg else away
        better_pct = max(h_fg, a_fg)
        if better_pct >= 50:
            summary += f" {better_team} shot {better_pct}% from the field."

    return summary