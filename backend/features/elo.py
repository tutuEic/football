# -*- coding: utf-8 -*-
"""
Elo Rating System for football teams.
Provides long-term strength assessment as features for other models.
"""
import sys, os, json, math
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query

ELO_FILE = Path(__file__).resolve().parent.parent / 'models' / 'elo_ratings.json'

# K-factor settings
K_BASE = 20
K_GOAL_DIFF_BONUS = 3  # Extra K per goal difference (max +9)
K_MAX = 35

# Home advantage in Elo points
HOME_ADVANTAGE_ELO = 65

# Season carryover
SEASON_CARRYOVER = 0.70
LEAGUE_AVG_ELO = 1500


class EloSystem:
    """Football Elo rating system."""

    def __init__(self, k_base=K_BASE, home_advantage=HOME_ADVANTAGE_ELO):
        self.k_base = k_base
        self.home_advantage = home_advantage
        self.ratings: dict[str, float] = {}
        self.history: list[dict] = []

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, LEAGUE_AVG_ELO)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def calculate_k(self, goal_diff: int) -> float:
        """K-factor with goal difference bonus."""
        bonus = min(abs(goal_diff), 3) * K_GOAL_DIFF_BONUS
        return min(self.k_base + bonus, K_MAX)

    def update(self, home: str, away: str, home_goals: int, away_goals: int):
        """Update ratings after a match."""
        r_home = self.get_rating(home)
        r_away = self.get_rating(away)

        # Expected scores (with home advantage)
        e_home = self.expected_score(r_home + self.home_advantage, r_away)
        e_away = 1 - e_home

        # Actual scores
        if home_goals > away_goals:
            s_home, s_away = 1.0, 0.0
        elif home_goals < away_goals:
            s_home, s_away = 0.0, 1.0
        else:
            s_home, s_away = 0.5, 0.5

        # K-factor
        goal_diff = home_goals - away_goals
        k = self.calculate_k(goal_diff)

        # Update
        delta_home = k * (s_home - e_home)
        delta_away = k * (s_away - e_away)

        self.ratings[home] = r_home + delta_home
        self.ratings[away] = r_away + delta_away

        self.history.append({
            "home": home, "away": away,
            "home_goals": home_goals, "away_goals": away_goals,
            "r_home_before": round(r_home, 1),
            "r_away_before": round(r_away, 1),
            "r_home_after": round(self.ratings[home], 1),
            "r_away_after": round(self.ratings[away], 1),
            "delta_home": round(delta_home, 1),
            "delta_away": round(delta_away, 1),
        })

    def season_rollover(self):
        """Apply season carryover: regress toward league average."""
        for team in self.ratings:
            self.ratings[team] = (
                self.ratings[team] * SEASON_CARRYOVER
                + LEAGUE_AVG_ELO * (1 - SEASON_CARRYOVER)
            )

    def save(self, path=None):
        path = Path(path) if path else ELO_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "ratings": {k: round(v, 1) for k, v in self.ratings.items()},
            "metadata": {
                "k_base": self.k_base,
                "home_advantage": self.home_advantage,
                "matches_processed": len(self.history),
            }
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def load(self, path=None):
        path = Path(path) if path else ELO_FILE
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            self.ratings = {k: float(v) for k, v in data.get("ratings", {}).items()}
            return True
        return False

    def build_from_history(self, league_code: str, seasons: list[str] = None):
        """Rebuild Elo ratings from match history."""
        if seasons is None:
            from data.match_repo import get_seasons
            all_s = get_seasons(league_code)
            seasons = sorted(all_s)[-3:] if len(all_s) >= 3 else all_s

        from data.match_repo import get_matches_for_training
        matches = get_matches_for_training(league_code, seasons)

        self.ratings = {}
        current_season = None

        for m in matches:
            # Detect season change (approximate by checking home team list)
            if m["home"] not in self.ratings and len(self.ratings) > 10:
                # Likely new season
                if current_season is None:
                    current_season = 1
                else:
                    self.season_rollover()
                    current_season += 1

            self.update(m["home"], m["away"],
                       int(m["home_goals"]), int(m["away_goals"]))

        self.save()
        print(f"Built Elo for {len(self.ratings)} teams from {len(matches)} matches")
        return self.ratings

    def get_top_teams(self, n=20):
        return sorted(self.ratings.items(), key=lambda x: -x[1])[:n]


def get_elo_rating(team: str, league: str = None) -> float:
    """Get Elo rating for a team (loads from file)."""
    elo = EloSystem()
    if elo.load():
        return elo.get_rating(team)
    return LEAGUE_AVG_ELO


def get_elo_diff(home: str, away: str) -> float:
    """Get Elo difference (home - away)."""
    return get_elo_rating(home) - get_elo_rating(away)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--league", default="E0")
    p.add_argument("--top", type=int, default=20)
    args = p.parse_args()

    elo = EloSystem()
    elo.build_from_history(args.league)
    print(f"\nTop {args.top} teams by Elo:")
    for team, rating in elo.get_top_teams(args.top):
        print(f"  {rating:6.0f}  {team}")
