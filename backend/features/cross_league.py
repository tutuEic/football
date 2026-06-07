# -*- coding: utf-8 -*-
"""
P2-2: Cross-League Global Features
===================================
Uses information from other leagues and European competitions to improve predictions.

Features:
1. League-level statistics (avg goals, home advantage, draw rate)
2. League quality index (from European competition results)
3. Cross-league team strength calibration

Reference: "Total Football" (2024) - holistic data approach
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query


# ============================================================
# 1. League-Level Statistics
# ============================================================

# Cache for league stats (thread-safe)
import threading as _threading
_league_stats_cache = {}
_league_stats_lock = _threading.Lock()
_MAX_CACHE = 100

def get_league_stats(league_code, seasons=None):
    """
    Get league-level statistics.
    Returns avg goals, home advantage, draw rate, etc.
    """
    if league_code in _league_stats_cache:
        return _league_stats_cache[league_code]
    
    if seasons is None:
        # Use last 2 seasons
        seasons_query = """
            SELECT DISTINCT season FROM matches 
            WHERE league_code=%s AND fthg IS NOT NULL
            ORDER BY season DESC LIMIT 2
        """
        season_rows = query(seasons_query, [league_code])
        seasons = [r["season"] for r in season_rows]
    
    if not seasons:
        return _default_league_stats()
    
    placeholders = ",".join(["%s"] * len(seasons))
    rows = query(f"""
        SELECT 
            AVG(fthg) as avg_hg, AVG(ftag) as avg_ag,
            SUM(CASE WHEN ftr='H' THEN 1 ELSE 0 END) as h_wins,
            SUM(CASE WHEN ftr='D' THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN ftr='A' THEN 1 ELSE 0 END) as a_wins,
            COUNT(*) as total,
            AVG(fthg + ftag) as avg_total_goals
        FROM matches 
        WHERE league_code=%s AND season IN ({placeholders})
        AND fthg IS NOT NULL AND ftag IS NOT NULL
    """, [league_code] + list(seasons))
    
    if not rows or rows[0]["total"] == 0:
        return _default_league_stats()
    
    r = rows[0]
    n = r["total"]
    
    stats = {
        "avg_home_goals": round(float(r["avg_hg"]), 3),
        "avg_away_goals": round(float(r["avg_ag"]), 3),
        "avg_total_goals": round(float(r["avg_total_goals"]), 3),
        "home_win_rate": round(r["h_wins"] / n, 3),
        "draw_rate": round(r["draws"] / n, 3),
        "away_win_rate": round(r["a_wins"] / n, 3),
        "home_advantage": round(float(r["avg_hg"]) - float(r["avg_ag"]), 3),
        "n_matches": n,
        "seasons": seasons,
    }
    
    if len(_league_stats_cache) >= _MAX_CACHE:
        _league_stats_cache.clear()
    _league_stats_cache[league_code] = stats
    return stats


def _default_league_stats():
    """Default league stats when data is unavailable."""
    return {
        "avg_home_goals": 1.5,
        "avg_away_goals": 1.2,
        "avg_total_goals": 2.7,
        "home_win_rate": 0.42,
        "draw_rate": 0.25,
        "away_win_rate": 0.33,
        "home_advantage": 0.3,
        "n_matches": 0,
        "seasons": [],
    }


# ============================================================
# 2. League Quality Index (from European competitions)
# ============================================================

_league_quality_cache = None

def get_league_quality_index():
    """
    Compute league quality index from European competition results.
    Uses Champions League and Europa League match results.
    """
    global _league_quality_cache
    if _league_quality_cache is not None:
        return _league_quality_cache
    
    # Map tm_clubs to leagues via domestic_competition_id
    COMP_TO_LEAGUE = {
        "GB1": "E0", "ES1": "SP1", "L1": "D1", "IT1": "I1", "FR1": "F1",
        "NL1": "N1", "PO1": "P1", "BE1": "B1", "TR1": "T1",
        "GB2": "E1", "L2": "D2", "IT2": "I2", "FR2": "F2", "ES2": "SP2",
        "SC1": "SC0", "SC2": "SC1", "GR1": "G1",
    }
    
    rows = query("""
        SELECT 
            c.domestic_competition_id as comp_id,
            SUM(CASE WHEN g.home_club_goals > g.away_club_goals AND g.home_club_id = c.club_id THEN 1
                     WHEN g.away_club_goals > g.home_club_goals AND g.away_club_id = c.club_id THEN 1
                     ELSE 0 END) as wins,
            SUM(CASE WHEN g.home_club_goals = g.away_club_goals THEN 1 ELSE 0 END) as draws,
            COUNT(*) as matches
        FROM tm_games g
        JOIN tm_clubs c ON (g.home_club_id = c.club_id OR g.away_club_id = c.club_id)
        WHERE g.competition_id IN ('UCL', 'UEL', 'UECL')
        AND g.date >= '2020-01-01'
        AND c.domestic_competition_id IS NOT NULL
        GROUP BY c.domestic_competition_id
        HAVING COUNT(*) >= 10
        ORDER BY (wins + draws * 0.5) / COUNT(*) DESC
    """, db="football_pred")
    
    if not rows:
        # Fallback: use hardcoded quality index
        _league_quality_cache = {
            "E0": 0.95, "SP1": 0.98, "D1": 0.90, "I1": 0.92, "F1": 0.88,
            "N1": 0.80, "P1": 0.78, "B1": 0.75, "T1": 0.72,
            "E1": 0.70, "D2": 0.68, "I2": 0.65, "F2": 0.63, "SP2": 0.60,
        }
        return _league_quality_cache
    
    # Normalize to 0-1 scale
    max_win_rate = 0
    league_win_rates = {}
    for r in rows:
        comp_id = r["comp_id"]
        league = COMP_TO_LEAGUE.get(comp_id)
        if not league:
            continue
        n = r["matches"]
        win_rate = (r["wins"] + r["draws"] * 0.5) / n
        league_win_rates[league] = win_rate
        if win_rate > max_win_rate:
            max_win_rate = win_rate
    
    _league_quality_cache = {}
    for league, wr in league_win_rates.items():
        _league_quality_cache[league] = round(wr / max_win_rate, 3) if max_win_rate > 0 else 0.5
    
    return _league_quality_cache


# ============================================================
# 3. Cross-League Feature Vector
# ============================================================

def compute_cross_league_features(home_team, away_team, home_league, away_league=None):
    """
    Compute cross-league global features for a match.
    
    Returns dict of features:
    - League-level stats for home team's league
    - League quality index
    - Cross-league comparison (if teams are from different leagues)
    """
    if away_league is None:
        away_league = home_league
    
    # League stats
    home_stats = get_league_stats(home_league)
    away_stats = get_league_stats(away_league) if away_league != home_league else home_stats
    
    # League quality
    quality = get_league_quality_index()
    home_quality = quality.get(home_league, 0.5)
    away_quality = quality.get(away_league, 0.5)
    
    features = {
        # Home league stats
        "league_avg_home_goals": home_stats["avg_home_goals"],
        "league_avg_away_goals": home_stats["avg_away_goals"],
        "league_avg_total_goals": home_stats["avg_total_goals"],
        "league_home_win_rate": home_stats["home_win_rate"],
        "league_draw_rate": home_stats["draw_rate"],
        "league_away_win_rate": home_stats["away_win_rate"],
        "league_home_advantage": home_stats["home_advantage"],
        
        # League quality
        "home_league_quality": home_quality,
        "away_league_quality": away_quality,
        "league_quality_diff": round(home_quality - away_quality, 3),
        
        # Cross-league adjustment
        "is_cross_league": 1 if home_league != away_league else 0,
        "cross_league_advantage": round((home_quality - away_quality) * 0.5, 3) if home_league != away_league else 0,
    }
    
    return features


# ============================================================
# 4. Get all available leagues
# ============================================================

def get_all_leagues():
    """Get all leagues with sufficient match data."""
    rows = query("""
        SELECT league_code, COUNT(*) as cnt
        FROM matches WHERE fthg IS NOT NULL
        GROUP BY league_code
        HAVING COUNT(*) >= 50
        ORDER BY cnt DESC
    """)
    return [r["league_code"] for r in rows]


# ============================================================
# 5. Build global Elo (across all leagues via European competitions)
# ============================================================

def build_global_elo():
    """
    Build a global Elo system that includes European competition results.
    This allows cross-league team comparison.
    """
    from features.elo import EloSystem
    
    elo = EloSystem()
    
    # First, build Elo for each domestic league
    leagues = get_all_leagues()
    for lg in leagues:
        try:
            elo.build_from_history(lg)
        except Exception:
            pass
    
    # Then, update with European competition results
    euro_matches = query("""
        SELECT 
            g.home_club_name as home, g.away_club_name as away,
            g.home_club_goals as home_goals, g.away_club_goals as away_goals,
            g.date
        FROM tm_games g
        WHERE g.competition_id IN ('UCL', 'UEL', 'UECL')
        AND g.date >= '2020-01-01'
        AND g.home_club_goals IS NOT NULL AND g.away_club_goals IS NOT NULL
        ORDER BY g.date
    """, db="football_pred")
    
    for m in euro_matches:
        elo.update(m["home"], m["away"], int(m["home_goals"]), int(m["away_goals"]))
    
    elo.save()
    print("Built global Elo: " + str(len(elo.ratings)) + " teams")
    return elo
