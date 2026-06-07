# -*- coding: utf-8 -*-
"""
Feature Store — central feature computation and caching.
Computes all features for a given match and caches results.
"""
import sys
import os
import time
import hashlib
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from features.elo import get_elo_rating
from features.cross_league import compute_cross_league_features

# Feature cache (in-memory, TTL=1h, thread-safe)
import threading as _threading
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = _threading.Lock()
CACHE_TTL = 3600  # seconds


def _cache_key(*args):
    raw = json.dumps(args, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key):
    with _cache_lock:
        if key in _cache:
            ts, data = _cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
        del _cache[key]
    return None


def _set_cached(key, data):
    _cache[key] = (time.time(), data)


# ============================================================
# Team features
# ============================================================

def get_team_form(team: str, league: str, n_matches: int = 5) -> dict:
    """Get team form (points, goals, results) over last N matches."""
    key = _cache_key("form", team, league, n_matches)
    cached = _get_cached(key)
    if cached:
        return cached

    rows = query("""
        SELECT match_date, ftr, home_team, away_team, fthg, ftag
        FROM matches
        WHERE league_code=%s AND (home_team=%s OR away_team=%s)
          AND ftr IS NOT NULL
        ORDER BY match_date DESC LIMIT %s
    """, [league, team, team, n_matches])

    points = 0
    goals_for = 0
    goals_against = 0
    wins = 0
    draws = 0
    losses = 0
    results = []

    for r in rows:
        is_home = r["home_team"] == team
        gf = r["fthg"] if is_home else r["ftag"]
        ga = r["ftag"] if is_home else r["fthg"]
        ftr = r["ftr"]

        goals_for += gf
        goals_against += ga

        if (is_home and ftr == "H") or (not is_home and ftr == "A"):
            points += 3
            wins += 1
            results.append("W")
        elif ftr == "D":
            points += 1
            draws += 1
            results.append("D")
        else:
            losses += 1
            results.append("L")

    n = len(rows) or 1
    result = {
        "points": points,
        "points_per_game": round(points / n, 2),
        "wins": wins, "draws": draws, "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_diff": goals_for - goals_against,
        "avg_goals_for": round(goals_for / n, 2),
        "avg_goals_against": round(goals_against / n, 2),
        "results": results,
        "matches_played": len(rows),
    }
    _set_cached(key, result)
    return result


def get_team_xg(team: str, league: str, n_matches: int = 10) -> dict:
    """Get team xG stats from match_stats if available."""
    key = _cache_key("xg", team, league, n_matches)
    cached = _get_cached(key)
    if cached:
        return cached

    rows = query("""
        SELECT ms.home_xg, ms.away_xg, f.home_team, f.away_team
        FROM match_stats ms
        JOIN fixtures f ON ms.fixture_id = f.id
        WHERE (f.home_team=%s OR f.away_team=%s)
        ORDER BY f.match_date DESC LIMIT %s
    """, [team, team, n_matches], db="football_pred")

    xg_for = []
    xg_against = []

    for r in rows:
        if r["home_team"] == team:
            xg_for.append(float(r["home_xg"] or 0))
            xg_against.append(float(r["away_xg"] or 0))
        else:
            xg_for.append(float(r["away_xg"] or 0))
            xg_against.append(float(r["home_xg"] or 0))

    result = {
        "xg_for": round(sum(xg_for) / max(len(xg_for), 1), 2),
        "xg_against": round(sum(xg_against) / max(len(xg_against), 1), 2),
        "xg_diff": round((sum(xg_for) - sum(xg_against)) / max(len(xg_for), 1), 2),
        "matches": len(xg_for),
    }
    _set_cached(key, result)
    return result


def get_h2h_stats(home: str, away: str, league: str, n: int = 10) -> dict:
    """Get head-to-head statistics."""
    key = _cache_key("h2h", home, away, league, n)
    cached = _get_cached(key)
    if cached:
        return cached

    rows = query("""
        SELECT fthg, ftag, ftr FROM matches
        WHERE league_code=%s
          AND ((home_team=%s AND away_team=%s) OR (home_team=%s AND away_team=%s))
          AND fthg IS NOT NULL
        ORDER BY match_date DESC LIMIT %s
    """, [league, home, away, away, home, n])

    h_wins = 0
    draws = 0
    a_wins = 0
    total_goals = 0

    for r in rows:
        total_goals += r["fthg"] + r["ftag"]
        home_is_home = (r["home_team"] == home)
        ftr = r["ftr"]
        if ftr == "D":
            draws += 1
        elif (ftr == "H" and home_is_home) or (ftr == "A" and not home_is_home):
            h_wins += 1
        else:
            a_wins += 1

    n_matches = len(rows) or 1
    result = {
        "matches": len(rows),
        "home_wins": h_wins,
        "draws": draws,
        "away_wins": a_wins,
        "avg_goals": round(total_goals / n_matches, 2),
    }
    _set_cached(key, result)
    return result




def get_match_odds(home_team: str, away_team: str, league: str) -> dict:
    """Fetch market odds for a match and convert to implied probabilities.
    Looks up by team names in the matches+odds join.
    Returns empty dict if no odds found (features will default to 0).
    """
    key = _cache_key("odds", home_team, away_team, league)
    cached = _get_cached(key)
    if cached:
        return cached

    # Try historical matches first (most reliable)
    rows = query("""
        SELECT o.avgh, o.avgd, o.avga
        FROM matches m
        JOIN odds o ON m.id = o.match_id
        WHERE m.league_code=%s
          AND m.home_team=%s AND m.away_team=%s
          AND o.avgh IS NOT NULL
        ORDER BY m.match_date DESC LIMIT 1
    """, [league, home_team, away_team])

    if not rows:
        # Try fixtures table for upcoming matches
        try:
            rows = query("""
                SELECT o.avgh, o.avgd, o.avga
                FROM fixtures m
                JOIN odds o ON m.id = o.match_id
                WHERE m.league_code=%s
                  AND m.home_team=%s AND m.away_team=%s
                  AND o.avgh IS NOT NULL
                LIMIT 1
            """, [league, home_team, away_team], db="football_pred")
    
        except Exception:
            rows = []
    if not rows:
        result = {}
        _set_cached(key, result)
        return result

    r = rows[0]
    odds_h = float(r["avgh"] or 0)
    odds_d = float(r["avgd"] or 0)
    odds_a = float(r["avga"] or 0)

    if odds_h <= 1.0 or odds_d <= 1.0 or odds_a <= 1.0:
        result = {}
        _set_cached(key, result)
        return result

    # Convert to implied probabilities (remove overround via normalization)
    raw_h = 1.0 / odds_h
    raw_d = 1.0 / odds_d
    raw_a = 1.0 / odds_a
    total = raw_h + raw_d + raw_a

    result = {
        "has_odds": 1,
        "odds_home": round(odds_h, 2),
        "odds_draw": round(odds_d, 2),
        "odds_away": round(odds_a, 2),
        "odds_implied_home": round(raw_h / total, 4),
        "odds_implied_draw": round(raw_d / total, 4),
        "odds_implied_away": round(raw_a / total, 4),
    }
    _set_cached(key, result)
    return result


def get_fixture_congestion(team: str, league: str, days: int = 14) -> dict:
    """Count matches played in the last N days (fixture congestion / fatigue indicator).
    Research shows 3+ matches in 14 days significantly reduces performance.
    """
    key = _cache_key("congestion", team, league, days)
    cached = _get_cached(key)
    if cached:
        return cached

    rows = query("""
        SELECT COUNT(*) as cnt
        FROM matches
        WHERE league_code=%s AND (home_team=%s OR away_team=%s)
          AND match_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
          AND ftr IS NOT NULL
    """, [league, team, team, days])

    cnt = rows[0]["cnt"] if rows and rows[0]["cnt"] else 0
    result = {"matches_14d": cnt}
    _set_cached(key, result)
    return result



def get_venue_form(team: str, league: str, venue: str, n_matches: int = 5) -> dict:
    """Get team form at a specific venue (home or away).
    venue='home' gets form in home matches, 'away' gets form in away matches.
    """
    key = _cache_key("venue_form", team, league, venue, n_matches)
    cached = _get_cached(key)
    if cached:
        return cached

    if venue == "home":
        where_clause = "home_team=%s"
    else:
        where_clause = "away_team=%s"

    rows = query(f"""
        SELECT match_date, ftr, home_team, away_team, fthg, ftag
        FROM matches
        WHERE league_code=%s AND {where_clause}
          AND ftr IS NOT NULL
        ORDER BY match_date DESC LIMIT %s
    """, [league, team, n_matches])

    points = 0
    goals_for = 0
    goals_against = 0
    n = len(rows) or 1

    for r in rows:
        is_home = r["home_team"] == team
        gf = r["fthg"] if is_home else r["ftag"]
        ga = r["ftag"] if is_home else r["fthg"]
        ftr = r["ftr"]

        goals_for += gf
        goals_against += ga

        if (is_home and ftr == "H") or (not is_home and ftr == "A"):
            points += 3
        elif ftr == "D":
            points += 1

    result = {
        "ppg": round(points / n, 2),
        "avg_gf": round(goals_for / n, 2),
        "avg_ga": round(goals_against / n, 2),
        "matches": len(rows),
    }
    _set_cached(key, result)
    return result


# ============================================================
# Composite feature vector
# ============================================================

def compute_match_features(home_team: str, away_team: str, league: str) -> dict:
    """
    Compute complete feature vector for a match.
    Returns dict of all features for model input.
    """
    # Elo features
    elo_home = get_elo_rating(home_team)
    elo_away = get_elo_rating(away_team)
    elo_diff = elo_home - elo_away

    # Form features
    form_home = get_team_form(home_team, league, 5)
    form_away = get_team_form(away_team, league, 5)
    form_10_home = get_team_form(home_team, league, 10)
    form_10_away = get_team_form(away_team, league, 10)

    # xG features
    xg_home = get_team_xg(home_team, league)
    xg_away = get_team_xg(away_team, league)

    # H2H features
    h2h = get_h2h_stats(home_team, away_team, league)

    # Market odds features
    odds = get_match_odds(home_team, away_team, league)

    # Fixture congestion (fatigue indicator)
    cong_home = get_fixture_congestion(home_team, league)
    cong_away = get_fixture_congestion(away_team, league)

    # Venue-specific form (home team at home, away team away)
    venue_home = get_venue_form(home_team, league, "home")
    venue_away = get_venue_form(away_team, league, "away")

    # Derived features
    form_diff = form_home["points_per_game"] - form_away["points_per_game"]
    goals_diff = form_home["avg_goals_for"] - form_away["avg_goals_for"]
    defence_diff = form_away["avg_goals_against"] - form_home["avg_goals_against"]
    xg_for_diff = xg_home["xg_for"] - xg_away["xg_for"]
    xg_against_diff = xg_away["xg_against"] - xg_home["xg_against"]

    # Cross-league global features
    cross = compute_cross_league_features(home_team, away_team, league)

    return {
        # Elo
        "elo_home": round(elo_home, 0),
        "elo_away": round(elo_away, 0),
        "elo_diff": round(elo_diff, 0),

        # Form (5 matches)
        "form_ppg_home": form_home["points_per_game"],
        "form_ppg_away": form_away["points_per_game"],
        "form_diff": round(form_diff, 2),
        "form_gf_home": form_home["avg_goals_for"],
        "form_gf_away": form_away["avg_goals_for"],
        "form_ga_home": form_home["avg_goals_against"],
        "form_ga_away": form_away["avg_goals_against"],
        "form_gd_home": form_home["goal_diff"],
        "form_gd_away": form_away["goal_diff"],

        # Form (10 matches)
        "form10_ppg_home": form_10_home["points_per_game"],
        "form10_ppg_away": form_10_away["points_per_game"],

        # xG
        "xg_for_home": xg_home["xg_for"],
        "xg_for_away": xg_away["xg_for"],
        "xg_against_home": xg_home["xg_against"],
        "xg_against_away": xg_away["xg_against"],
        "xg_for_diff": round(xg_for_diff, 2),
        "xg_against_diff": round(xg_against_diff, 2),

        # H2H
        "h2h_matches": h2h["matches"],
        "h2h_home_wins_pct": round(h2h["home_wins"] / max(h2h["matches"], 1), 2),
        "h2h_draw_pct": round(h2h["draws"] / max(h2h["matches"], 1), 2),
        "h2h_avg_goals": h2h["avg_goals"],

        # Composite
        "goals_diff": round(goals_diff, 2),
        "defence_diff": round(defence_diff, 2),

        # Fixture congestion (fatigue)
        "congestion_home": cong_home["matches_14d"],
        "congestion_away": cong_away["matches_14d"],
        "congestion_diff": cong_home["matches_14d"] - cong_away["matches_14d"],

        # Venue-specific form
        "venue_form_home": venue_home["ppg"],
        "venue_form_away": venue_away["ppg"],
        "venue_form_diff": round(venue_home["ppg"] - venue_away["ppg"], 2),

        # Market odds (implied probabilities; default 0.33 when no odds)
        "has_odds": odds.get("has_odds", 0),
        "odds_implied_home": odds.get("odds_implied_home", 0.333),
        "odds_implied_draw": odds.get("odds_implied_draw", 0.333),
        "odds_implied_away": odds.get("odds_implied_away", 0.333),

        # Home advantage indicator
        "is_home": 1,

        # Cross-league global features
        "league_avg_goals": cross["league_avg_total_goals"],
        "league_home_advantage": cross["league_home_advantage"],
        "league_draw_rate": cross["league_draw_rate"],
        "home_league_quality": cross["home_league_quality"],
        "away_league_quality": cross["away_league_quality"],
        "league_quality_diff": cross["league_quality_diff"],
    }


# Feature names for model training
FEATURE_NAMES = [
    "elo_diff",
    "form_diff", "form_ppg_home", "form_ppg_away",
    "form_gf_home", "form_gf_away", "form_ga_home", "form_ga_away",
    "form10_ppg_home", "form10_ppg_away",
    "xg_for_diff", "xg_against_diff",
    "xg_for_home", "xg_for_away", "xg_against_home", "xg_against_away",
    "h2h_home_wins_pct", "h2h_draw_pct", "h2h_avg_goals",
    "goals_diff", "defence_diff",
    "congestion_home", "congestion_away", "congestion_diff",
    "venue_form_home", "venue_form_away", "venue_form_diff",
    "has_odds", "odds_implied_home", "odds_implied_draw", "odds_implied_away",
    # Cross-league global features
    "league_avg_goals", "league_home_advantage", "league_draw_rate",
    "home_league_quality", "away_league_quality", "league_quality_diff",
]


def get_feature_vector(home_team: str, away_team: str, league: str) -> list:
    """Get feature vector as list (for model input)."""
    features = compute_match_features(home_team, away_team, league)
    return [features.get(f, 0) for f in FEATURE_NAMES]
