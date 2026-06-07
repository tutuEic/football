# -*- coding: utf-8 -*-
"""Match statistics API - recent form, H2H, standings."""
from fastapi import APIRouter, Query
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query
router = APIRouter()


@router.get("/matches/leagues")
def list_leagues():
    """League list."""
    from data.match_repo import get_all_leagues
    return {"status": "ok", "leagues": get_all_leagues()}


@router.get("/matches/recent")
def recent_form(team: str = Query(...), league: str = "E0", limit: int = 10):
    """Recent results for a team."""
    # SQL has 4 placeholders: league_code, home_team, away_team, limit.
    # 'team' appears twice because the WHERE clause matches
    # on EITHER home_team or away_team.
    rows = query("""
        SELECT match_date, home_team, away_team, fthg, ftag, ftr
        FROM matches
        WHERE league_code=%s
          AND (home_team=%s OR away_team=%s)
          AND fthg IS NOT NULL
        ORDER BY match_date DESC
        LIMIT %s
    """, [
        league,   # -> league_code=%s
        team,     # -> home_team=%s
        team,     # -> away_team=%s
        limit,    # -> LIMIT %s
    ])
    
    results = []
    for r in rows:
        is_home = r["home_team"] == team
        gf = r["fthg"] if is_home else r["ftag"]
        ga = r["ftag"] if is_home else r["fthg"]
        if gf > ga: outcome = "W"
        elif gf < ga: outcome = "L"
        else: outcome = "D"
        results.append({
            "date": str(r["match_date"]),
            "opponent": r["away_team"] if is_home else r["home_team"],
            "home_away": "H" if is_home else "A",
            "score": f"{r['fthg']}-{r['ftag']}",
            "goals_for": gf, "goals_against": ga,
            "outcome": outcome,
        })
    
    wins = sum(1 for r in results if r["outcome"] == "W")
    draws = sum(1 for r in results if r["outcome"] == "D")
    losses = sum(1 for r in results if r["outcome"] == "L")
    return {"status": "ok", 
        "team": team, "league": league,
        "recent": results,
        "summary": f"{wins}W {draws}D {losses}L"
    }


@router.get("/matches/h2h")
def head_to_head(team1: str, team2: str, league: str = "E0", limit: int = 10):
    """Head-to-head history between two teams."""
    rows = query("""
        SELECT match_date, home_team, away_team, fthg, ftag
        FROM matches
        WHERE league_code=%s
          AND ((home_team=%s AND away_team=%s) OR (home_team=%s AND away_team=%s))
          AND fthg IS NOT NULL
        ORDER BY match_date DESC
        LIMIT %s
    """, [league, team1, team2, team2, team1, limit])
    
    results = []
    for r in rows:
        results.append({
            "date": str(r["match_date"]),
            "home": r["home_team"], "away": r["away_team"],
            "score": f"{r['fthg']}-{r['ftag']}",
        })
    
    return {"status": "ok", "team1": team1, "team2": team2, "h2h": results}


@router.get("/matches/standings")
def standings(league: str = "E0", season: str = None):
    """League table computed in real-time from matches table."""
    if season is None:
        seasons = query(
            "SELECT DISTINCT season FROM matches WHERE league_code=%s ORDER BY season DESC LIMIT 1",
            [league]
        )
        season = seasons[0]["season"] if seasons else "2526"
    
    rows = query("""
        SELECT home_team, away_team, fthg, ftag
        FROM matches
        WHERE league_code=%s AND season=%s AND fthg IS NOT NULL
    """, [league, season])
    
    table = {}
    for r in rows:
        for team, gf, ga in [
            (r["home_team"], r["fthg"], r["ftag"]),
            (r["away_team"], r["ftag"], r["fthg"])
        ]:
            if team not in table:
                table[team] = {"team": team, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0}
            t = table[team]
            t["P"] += 1; t["GF"] += gf; t["GA"] += ga
            if gf > ga: t["W"] += 1; t["Pts"] += 3
            elif gf == ga: t["D"] += 1; t["Pts"] += 1
            else: t["L"] += 1
    
    standings_list = sorted(table.values(), key=lambda x: (-x["Pts"], -(x["GF"]-x["GA"]), -x["GF"]))
    for i, t in enumerate(standings_list):
        t["pos"] = i + 1
        t["GD"] = t["GF"] - t["GA"]
    
    return {"status": "ok", "league": league, "season": season, "standings": standings_list}


@router.get("/matches/upcoming")
def upcoming_fixtures(league: str = Query(None), limit: int = Query(20, ge=1, le=100)):
    """Upcoming fixtures."""
    where = "WHERE (status IS NULL OR status != 'finished')"
    params = []
    if league:
        where += " AND league_code=%s"
        params.append(league)
    
    rows = query(f"""
        SELECT league_code, match_date, home_team, away_team, home_score, away_score, status
        FROM fixtures
        {where}
        ORDER BY match_date ASC
        LIMIT %s
    """, params + [limit], db="football_pred")
    
    results = []
    for r in rows:
        results.append({
            "league": r["league_code"],
            "date": str(r["match_date"]),
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "score": f"{r['home_score']}-{r['away_score']}" if r['home_score'] is not None else None,
            "status": r["status"] or "scheduled",
        })
    
    return {"status": "ok", "fixtures": results}
