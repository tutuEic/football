"""淇变箰閮?API 鈥?TM + fixtures 鍙屾簮鎼滅储"""
from fastapi import APIRouter, Query
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query
from data.tm_repo import search_club, get_club, get_club_squad, FBD_LEAGUE_TO_TM
from engine.player_ratings import get_club_squad_rated

router = APIRouter()

LEAGUE_NAMES_TM = {
    "GB1": "Premier League", "GB2": "Championship", "GB3": "League One", "GB4": "League Two",
    "ES1": "La Liga", "ES2": "Segunda Division", "IT1": "Serie A", "IT2": "Serie B",
    "FR1": "Ligue 1", "FR2": "Ligue 2", "L1": "Bundesliga", "L2": "2. Bundesliga",
    "NL1": "Eredivisie", "BE1": "Belgian Pro League", "PO1": "Primeira Liga", "TR1": "Super Lig",
    "GR1": "Super League Greece", "SC1": "Scottish Premiership", "MLS1": "MLS", "BRA1": "Brasileirao",
    "ARG1": "Argentine Primera", "JAP1": "J-League", "PL1": "Ekstraklasa", "RU1": "Russian Premier League",
    "DK1": "Danish Superliga", "UKR1": "Ukrainian Premier League", "SA1": "Saudi Pro League", "COL1": "Liga BetPlay",
}

LEAGUE_NAMES_FBD = {
    "E0": "Premier League", "E1": "Championship", "E2": "League One", "E3": "League Two",
    "SP1": "La Liga", "SP2": "Segunda Division", "D1": "Bundesliga", "D2": "2. Bundesliga",
    "I1": "Serie A", "I2": "Serie B", "F1": "Ligue 1", "F2": "Ligue 2",
    "N1": "Eredivisie", "P1": "Primeira Liga", "B1": "Belgian Pro League", "T1": "Super Lig",
    "SC0": "Scottish Premiership", "G1": "Super League Greece", "USA": "MLS", "JPN": "J-League",
}

# ---- 闈欐€佽矾鐢卞繀椤诲湪鍔ㄦ€佽矾鐢变箣鍓?----

@router.get("/clubs/leagues")
def list_club_leagues():
    """杩斿洖鎵€鏈夎仈璧涳紙TM + fixtures 鍙屾簮鍚堝苟锛"""
    # TM 婧?
    tm_rows = query("""
        SELECT domestic_competition_id, COUNT(*) as club_count
        FROM tm_clubs WHERE domestic_competition_id != ''
        GROUP BY domestic_competition_id ORDER BY club_count DESC
    """, db="football_pred")

    leagues = {}
    for r in tm_rows:
        tid = r["domestic_competition_id"]
        leagues[tid] = {
            "id": tid,
            "name": LEAGUE_NAMES_TM.get(tid, tid),
            "club_count": r["club_count"],
            "source": "transfermarkt"
        }

    # Fixtures 婧愶紙琛ュ厖 TM 娌℃湁鐨勮仈璧涳級
    fix_rows = query("""
        SELECT league_code, COUNT(DISTINCT home_team) as club_count
        FROM fixtures GROUP BY league_code ORDER BY club_count DESC
    """, db="football_pred")

    for r in fix_rows:
        lc = r["league_code"]
        tm_id = FBD_LEAGUE_TO_TM.get(lc, lc)
        if tm_id not in leagues:
            leagues[tm_id] = {
                "id": tm_id,
                "name": LEAGUE_NAMES_FBD.get(lc, lc),
                "club_count": r["club_count"],
                "source": "fixtures"
            }
        else:
            # 鍙栬緝澶х殑 club_count
            leagues[tm_id]["club_count"] = max(leagues[tm_id]["club_count"], r["club_count"])

    return sorted(leagues.values(), key=lambda x: -x["club_count"])


@router.get("/clubs/by-league")
def clubs_by_league(competition_id: str = Query(...), limit: int = 50):
    """鎸夎仈璧涚瓫閫変勘涔愰儴锛圱M浼樺厛锛宖ixtures鍥為€€锛"""
    # 鍏堟煡 TM
    tm_rows = query("""
        SELECT club_id, name, squad_size, total_market_value,
               average_age, stadium_name, coach_name
        FROM tm_clubs WHERE domestic_competition_id = %s
        ORDER BY total_market_value DESC LIMIT %s
    """, [competition_id, limit], db="football_pred")

    if tm_rows:
        for r in tm_rows:
            r["source"] = "transfermarkt"
        return {"competition_id": competition_id, "clubs": tm_rows, "source": "transfermarkt"}

    # TM 娌℃湁 鈫?鏌?fixtures
    from data.tm_repo import FBD_LEAGUE_TO_TM
    fbd_code = None
    for fbd, tm in FBD_LEAGUE_TO_TM.items():
        if tm == competition_id:
            fbd_code = fbd
            break

    if fbd_code:
        fix_rows = query("""
            SELECT DISTINCT home_team AS name, league_code
            FROM fixtures WHERE league_code = %s
            ORDER BY home_team LIMIT %s
        """, [fbd_code, limit], db="football_pred")
        clubs = []
        for r in fix_rows:
            clubs.append({
                "club_id": 0, "name": r["name"],
                "squad_size": 0, "total_market_value": 0,
                "average_age": 0, "stadium_name": "", "coach_name": "",
                "source": "fixtures"
            })
        return {"competition_id": competition_id, "clubs": clubs, "source": "fixtures"}

    return {"competition_id": competition_id, "clubs": [], "source": "none"}


@router.get("/clubs/search")
def search_club_endpoint(q: str = Query(...), limit: int = 10):
    """鎼滅储淇变箰閮紙TM + fixtures 鍙屾簮锛"""
    results = search_club(q, limit)
    # 琛ュ厖鑱旇禌涓枃鍚?
    for r in results:
        tm_id = r.get("domestic_competition_id", "")
        r["league_name"] = LEAGUE_NAMES_TM.get(tm_id, "") or LEAGUE_NAMES_FBD.get(r.get("league_code", ""), "")
    return {"query": q, "count": len(results), "clubs": results}


# ---- 鍔ㄦ€佽矾鐢辨斁鏈€鍚?----

@router.get("/clubs/{club_id}")
def club_detail(club_id: int):
    club = get_club(club_id)
    if not club:
        return {"status": "error", "message": f"Club {club_id} not found"}
    return club


@router.get("/clubs/{club_id}/squad")
def club_squad(club_id: int, name: str = None):
    """淇变箰閮ㄩ樀瀹癸紙鍚瘎鍒?+ 浣嶇疆鍒嗙被锛夈€俷ame 鐢ㄤ簬 fixtures 婧愪勘涔愰儴鍥為€€"""
    if club_id == 0 and name:
        club_name = name
    else:
        club = get_club(club_id)
        club_name = club.get("name", "") if club else None
    squad = get_club_squad_rated(club_id, club_name)

    #  If no TM data, try FIFA20 data, then estimator
    if not squad and club_name:
        from engine.squad_fifa import generate_squad_from_fifa
        squad = generate_squad_from_fifa(club_name)

    return {
        "club_id": club_id,
        "club_name": club_name or "",
        "count": len(squad), "players": squad,
    }


# ===== 鏃燭M鏁版嵁鐨勯€氱敤闃靛 =====

def _generate_generic_squad(club_name):
    """涓烘病鏈?TM 鏁版嵁鐨勪勘涔愰儴鐢熸垚鍗犱綅鐞冨憳"""
    players = []
    tmpl = [
        ("Goalkeeper 1", "Goalkeeper", "GK", 65, 15, 75),
        ("Goalkeeper 2", "Goalkeeper", "GK", 60, 15, 70),
        ("Centre-Back 1", "Centre-Back", "DF", 68, 25, 80),
        ("Centre-Back 2", "Centre-Back", "DF", 66, 25, 78),
        ("Centre-Back 3", "Centre-Back", "DF", 64, 25, 76),
        ("Left-Back 1", "Left-Back", "DF", 65, 45, 70),
        ("Right-Back 1", "Right-Back", "DF", 65, 45, 70),
        ("Central Mid 1", "Central Midfield", "MF", 70, 60, 60),
        ("Central Mid 2", "Central Midfield", "MF", 68, 58, 58),
        ("Central Mid 3", "Central Midfield", "MF", 66, 55, 55),
        ("Defensive Mid 1", "Defensive Midfield", "MF", 67, 40, 72),
        ("Attacking Mid 1", "Attacking Midfield", "MF", 69, 75, 35),
        ("Left Winger 1", "Left Winger", "FW", 68, 78, 25),
        ("Right Winger 1", "Right Winger", "FW", 68, 78, 25),
        ("Forward 1", "Centre-Forward", "FW", 72, 85, 20),
        ("Forward 2", "Centre-Forward", "FW", 68, 80, 20),
        ("Forward 3", "Centre-Forward", "FW", 65, 78, 20),
    ]
    for i, (sfx, pos, cat, ovr, atk, df) in enumerate(tmpl):
        players.append({
            "id": f"gen:{club_name}:{i}",
            "name": f"{club_name} {sfx}",
            "position": pos, "category": cat,
            "club": club_name, "overall": ovr,
            "attack_rating": atk, "defense_rating": df,
            "att": None, "market_value": "N/A",
            "goals_per_90": 0, "assists_per_90": 0,
            "appearances": 0, "source": "generic",
        })
    return players


# ===== 鏈€杩戞瘮璧涢樀瀹?=====

@router.get("/clubs/{club_id}/recent-lineup")
def club_recent_lineup(club_id: int, name: str = None):
    """鑾峰彇淇变箰閮ㄦ渶杩戜竴鍦烘瘮璧涚殑棣栧彂闃靛鍜岄樀鍨"""
    if club_id == 0 and name:
        team_name = name
    else:
        club = get_club(club_id)
        team_name = club.get("name", "") if club else None

    if not team_name:
        return {"status": "error", "message": "Club not found"}

    #  Normalize team name for fixtures matching
    # TM full names 鈫?football-data.co.uk short names
    tm_to_fbd = {
        "manchester city football club": "Man City",
        "manchester united football club": "Man United",
        "tottenham hotspur football club": "Tottenham",
        "newcastle united football club": "Newcastle",
        "aston villa football club": "Aston Villa",
        "arsenal football club": "Arsenal",
        "chelsea football club": "Chelsea",
        "liverpool football club": "Liverpool",
    }
    search_name = team_name
    key = team_name.lower()
    if key in tm_to_fbd:
        search_name = tm_to_fbd[key]
    # Also try just the first word for single-word clubs
    first_word = team_name.split()[0] if team_name else ""

    # 浠?fixtures 鏌ユ渶杩戞瘮璧?+ tm_games 鏌ラ樀鍨?
    from data.mysql_client import query
    fixtures = query("""
        SELECT home_team, away_team, match_date, home_score, away_score, id
        FROM football_pred.fixtures
        WHERE (home_team = %s OR away_team = %s OR home_team = %s OR away_team = %s)
          AND status = 'finished'
        ORDER BY match_date DESC LIMIT 3
    """, [search_name, search_name, first_word, first_word], db="football_pred")

    if not fixtures:
        return {"status": "error", "message": f"No recent matches found for {team_name}"}

    latest = fixtures[0]
    # Determine if this team was home or away in the match
    is_home = latest["home_team"] in (search_name, first_word, team_name)
    formation_str = None

    # Try tm_games for formation
    tm_rows = query("""
        SELECT home_club_formation, away_club_formation
        FROM football_pred.tm_games
        WHERE home_club_name = %s AND away_club_name LIKE %s AND date = %s
        LIMIT 1
    """, [latest["home_team"], f"%{latest['away_team']}%", str(latest["match_date"])], db="football_pred")
    if tm_rows:
        formation_str = tm_rows[0]["home_club_formation"] if is_home else tm_rows[0]["away_club_formation"]

    return {
        "team": team_name,
        "match": {
            "date": str(latest["match_date"]),
            "opponent": latest["away_team"] if is_home else latest["home_team"],
            "score": f"{latest['home_score']}-{latest['away_score']}",
            "home": is_home,
        },
        "formation": formation_str or None,
        "recent_matches": [
            {
                "date": str(r["match_date"]),
                "opponent": r["away_team"] if r["home_team"] == team_name else r["home_team"],
                "score": f"{r['home_score']}-{r['away_score']}",
            }
            # for r in fixtures
        ],
    }
