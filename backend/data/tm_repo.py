"""
Transfermarkt data repo — queries players/clubs from football_pred
Supports fixtures table fallback when TM data doesn't cover a league
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query

FBD_LEAGUE_TO_TM = {
    "E0": "GB1", "E1": "GB2", "E2": "GB3", "E3": "GB4",
    "SP1": "ES1", "SP2": "ES2",
    "D1": "L1", "D2": "L2",
    "I1": "IT1", "I2": "IT2",
    "F1": "FR1", "F2": "FR2",
    "N1": "NL1", "P1": "PO1", "B1": "BE1", "T1": "TR1",
    "SC0": "SC1", "G1": "GR1", "USA": "MLS1", "JPN": "JAP1",
}

def search_players(name, limit=20):
    return query(
        """SELECT player_id, name, position, sub_position, current_club_name,
                  market_value_in_eur, foot, height_in_cm, country_of_citizenship
           FROM tm_players WHERE name LIKE %s
           ORDER BY market_value_in_eur DESC LIMIT %s""",
        [f"%{name}%", limit], db="football_pred"
    )

def get_player(player_id):
    rows = query("SELECT * FROM tm_players WHERE player_id=%s", [player_id], db="football_pred")
    return rows[0] if rows else None

def get_player_stats(player_id):
    sql = """
        SELECT player_id, MAX(player_name) AS player_name,
            COUNT(*) AS appearances, SUM(goals) AS total_goals,
            SUM(assists) AS total_assists, SUM(minutes_played) AS total_minutes,
            SUM(yellow_cards) AS yellow_cards, SUM(red_cards) AS red_cards,
            ROUND(SUM(goals)/NULLIF(SUM(minutes_played),0)*90,3) AS goals_per_90,
            ROUND(SUM(assists)/NULLIF(SUM(minutes_played),0)*90,3) AS assists_per_90
        FROM tm_appearances WHERE player_id = %s GROUP BY player_id"""
    return query(sql, [player_id], db="football_pred")

def get_club_squad(club_id, limit=30):
    if club_id == 0:
        return []
    return query(
        """SELECT player_id, name, position, sub_position, market_value_in_eur, foot
           FROM tm_players WHERE current_club_id = %s
           ORDER BY market_value_in_eur DESC LIMIT %s""",
        [club_id, limit], db="football_pred"
    )

# ===== Club search (TM + fixtures fallback) =====

def search_club(name, limit=10):
    results = _search_tm_clubs(name, limit)
    if results:
        return results
    return _search_fixture_teams(name, limit)

def _search_tm_clubs(name, limit=10):
    # Try exact match first
    results = query(
        """SELECT club_id, name, domestic_competition_id, squad_size,
                  total_market_value, average_age, stadium_name, coach_name
           FROM tm_clubs WHERE name LIKE %s
           ORDER BY total_market_value DESC LIMIT %s""",
        [f"%{name}%", limit], db="football_pred"
    )
    if results:
        for r in results:
            r["source"] = "transfermarkt"
        return results

    # Multi-word search: single query with OR conditions
    words = [w for w in name.split() if len(w) >= 3]
    if len(words) > 1:
        conditions = " OR ".join(["name LIKE %s"] * len(words))
        params = [f"%{w}%" for w in words]
        params.append(limit)
        results = query(
            f"""SELECT club_id, name, domestic_competition_id, squad_size,
                      total_market_value, average_age, stadium_name, coach_name
               FROM tm_clubs WHERE {conditions}
               ORDER BY total_market_value DESC LIMIT %s""",
            params, db="football_pred"
        )
        if results:
            for r in results:
                r["source"] = "transfermarkt"
            return results
    return []

def _search_fixture_teams(name, limit=10):
    results = query(
        """SELECT DISTINCT home_team AS name, league_code
           FROM fixtures WHERE home_team LIKE %s
           ORDER BY league_code LIMIT %s""",
        [f"%{name}%", limit], db="football_pred"
    )
    if not results:
        words = [w for w in name.split() if len(w) >= 3]
        if len(words) > 1:
            best = []
            for word in words:
                r = query(
                    """SELECT DISTINCT home_team AS name, league_code
                       FROM fixtures WHERE home_team LIKE %s LIMIT %s""",
                    [f"%{word}%", limit], db="football_pred"
                )
                best.extend(r)
            if best:
                from collections import Counter
                counts = Counter(b["name"] for b in best)
                best.sort(key=lambda c: -counts[c["name"]])
                seen = set(); results = []
                for c in best:
                    if c["name"] not in seen:
                        seen.add(c["name"]); results.append(c)
                results = results[:limit]
    for r in results:
        r["club_id"] = 0
        r["domestic_competition_id"] = FBD_LEAGUE_TO_TM.get(r.get("league_code",""), r.get("league_code",""))
        r["squad_size"] = 0
        r["total_market_value"] = 0
        r["average_age"] = 0
        r["stadium_name"] = ""
        r["coach_name"] = ""
        r["source"] = "fixtures"
    return results

def get_club(club_id):
    if club_id == 0:
        return None
    rows = query("SELECT * FROM tm_clubs WHERE club_id=%s", [club_id], db="football_pred")
    return rows[0] if rows else None

def get_player_recent_games(player_id, limit=10):
    return query("""
        SELECT a.game_id, a.goals, a.assists, a.minutes_played,
               g.date, g.home_club_name, g.away_club_name,
               g.home_club_goals, g.away_club_goals
        FROM tm_appearances a JOIN tm_games g ON a.game_id = g.game_id
        WHERE a.player_id = %s ORDER BY g.date DESC LIMIT %s
    """, [player_id, limit], db="football_pred")
