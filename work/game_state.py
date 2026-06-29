from __future__ import annotations


class GameState:
    def __init__(self):
        self.last_event_id = None
        self.score_home = 0
        self.score_away = 0
        self.period = 0
        self.clock = ""
        self.current_run_team = None
        self.current_run_points = 0
        self.plays_processed = 0
        self.home_tricode = None  # ADD THIS
        self.away_tricode = None  # ADD THIS

    def update(self, play):
        old_leader = self._leader()

        if play["score_home"] is not None:
            self.score_home = play["score_home"]
        if play["score_away"] is not None:
            self.score_away = play["score_away"]

        self.period = play["period"] or self.period
        self.clock = play["clock"] or self.clock
        self.last_event_id = play["id"]
        self.plays_processed += 1

        # ADD THIS BLOCK — learn tricodes from plays as they come in
        team = play.get("team")
        if team and play.get("score_home") is not None and play.get("score_away") is not None:
            # We can't know home vs away from a play alone, so we track
            # tricodes from the summary instead (set externally)
            pass

        new_leader = self._leader()
        lead_changed = old_leader is not None and new_leader is not None and old_leader != new_leader
        self._update_run(play)

        return {
            "score_home": self.score_home,
            "score_away": self.score_away,
            "period": self.period,
            "clock": self.clock,
            "leader": new_leader,
            "lead_changed": lead_changed,
            "current_run_team": self.current_run_team,
            "current_run_points": self.current_run_points,
            "plays_processed": self.plays_processed,
        }

    def _leader(self):
        if self.score_home > self.score_away:
            return "home"
        if self.score_away > self.score_home:
            return "away"
        return None

    def _update_run(self, play):
        if play["points"] <= 0 or not play["team"]:
            return
        if self.current_run_team == play["team"]:
            self.current_run_points += play["points"]
            return
        self.current_run_team = play["team"]
        self.current_run_points = play["points"]