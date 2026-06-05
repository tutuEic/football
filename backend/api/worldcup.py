# -*- coding: utf-8 -*-
"""
World Cup API — REST endpoints for WC2026 prediction module
============================================================
Endpoints:
  GET  /worldcup/groups           — All 12 groups with standings + predictions
  GET  /worldcup/groups/{name}    — Single group detail
  GET  /worldcup/matches          — All WC2026 matches (filterable)
  GET  /worldcup/matches/{id}     — Single match + prediction
  GET  /worldcup/predictions      — All group match predictions
  POST /worldcup/predict          — Predict a custom matchup
  POST /worldcup/simulate         — Run full tournament simulation
  GET  /worldcup/simulate/result  — Get latest simulation result
  GET  /worldcup/rankings         — All 48 teams ranked by strength
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query
from engine.wc_data import analyze_squad, analyze_all_wc_teams
from engine.wc_predictor import predict_wc_match
from engine.wc_simulator import simulate_tournament, format_simulation_report, load_groups
from engine.wc_elo_adapter import analyze_squad_elo, clear_elo_cache
from engine.wc_knockout import simulate_bracket_n_times, get_golden_ball_candidates, analyze_group_upsets

router = APIRouter(prefix="/worldcup")

# Module-level caches
_simulation_result = None
_simulation_time = None
_rankings_cache = None
_rankings_time = None


# ============================================================
# Request Models
# ============================================================

class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    stage: str = "group"
    matchday: int = 1
    is_host: bool = False


class KnockoutRequest(BaseModel):
    n_sims: int = 100


class SimulateRequest(BaseModel):
    n_sims: int = 1000


# ============================================================
# Groups
# ============================================================

@router.get("/groups")
def get_all_groups():
    """Get all 12 WC groups with team info and group-level predictions."""
    groups = load_groups()
    result = []

    for gn in sorted(groups.keys()):
        teams_info = []
        for t in groups[gn]:
            # Get squad analysis for each team
            try:
                analysis = analyze_squad(t["team"])
                teams_info.append({
                    "team": t["team"],
                    "confederation": t["confederation"],
                    "fifa_ranking": t["fifa_ranking"],
                    "elo_rating": t["elo_rating"],
                    "is_host": bool(t["is_host"]),
                    "starting_xi": analysis["starting_xi"],
                    "elo_bonus": analysis["elo_bonus"],
                    "top_players": analysis["top_players"][:3],
                })
            except Exception:
                teams_info.append({
                    "team": t["team"],
                    "confederation": t["confederation"],
                    "fifa_ranking": t["fifa_ranking"],
                    "elo_rating": t["elo_rating"],
                    "is_host": bool(t["is_host"]),
                    "starting_xi": 50,
                    "elo_bonus": 0,
                    "top_players": [],
                })

        result.append({
            "group": gn,
            "teams": teams_info,
        })

    return {"status": "ok", "groups": result}


@router.get("/groups/{group_name}")
def get_group_detail(group_name: str):
    """Get detailed group info with all head-to-head predictions."""
    groups = load_groups()
    gn = group_name.upper()

    if gn not in groups:
        raise HTTPException(status_code=404, detail=f"Group {gn} not found")

    teams = groups[gn]
    team_names = [t["team"] for t in teams]

    # Predict all 6 head-to-head matches
    predictions = []
    for i in range(len(team_names)):
        for j in range(i + 1, len(team_names)):
            h, a = team_names[i], team_names[j]
            try:
                pred = predict_wc_match(h, a, {
                    "stage": "group", "matchday": 1,
                    "is_host": any(t["team"] == h and t.get("is_host") for t in teams),
                    "in_host_country": True,
                })
                predictions.append({
                    "home": h, "away": a,
                    "expected_goals": pred["expected_goals"],
                    "wdl": pred["wdl"],
                    "most_likely_score": pred["most_likely_score"],
                })
            except Exception as e:
                predictions.append({"home": h, "away": a, "error": str(e)})

    return {
        "status": "ok",
        "group": gn,
        "teams": [{"team": t["team"], "confederation": t["confederation"],
                   "fifa_ranking": t["fifa_ranking"], "elo_rating": t["elo_rating"],
                   "is_host": bool(t["is_host"])} for t in teams],
        "predictions": predictions,
    }


# ============================================================
# Matches
# ============================================================

@router.get("/matches")
def get_matches(
    status: Optional[str] = Query(None, description="Filter by status: scheduled, finished"),
    limit: int = Query(100, ge=1, le=200),
):
    """Get all WC2026 fixtures."""
    where = "WHERE league_code = 'WC2026'"
    params = []
    if status:
        where += " AND status = %s"
        params.append(status)

    rows = query(f"""
        SELECT id, match_date, home_team, away_team, home_score, away_score, status
        FROM fixtures
        {where}
        ORDER BY match_date ASC, id ASC
        LIMIT %s
    """, params + [limit], db="football_pred")

    matches = []
    for r in rows:
        matches.append({
            "fixture_id": r["id"],
            "date": str(r["match_date"]),
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "home_score": r["home_score"],
            "away_score": r["away_score"],
            "status": r["status"] or "scheduled",
        })

    return {"status": "ok", "count": len(matches), "matches": matches}


@router.get("/matches/{fixture_id}")
def get_match_detail(fixture_id: int):
    """Get single match with full prediction."""
    rows = query(
        "SELECT * FROM fixtures WHERE id = %s AND league_code = 'WC2026'",
        [fixture_id], db="football_pred"
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Match not found")

    f = rows[0]
    home, away = f["home_team"], f["away_team"]

    # Get group info
    group_rows = query(
        "SELECT group_name FROM wc_groups WHERE team = %s",
        [home], db="football_pred"
    )
    group = group_rows[0]["group_name"] if group_rows else None

    # Check if host
    host_rows = query("SELECT team FROM wc_groups WHERE is_host = 1", db="football_pred")
    host_teams = {r["team"] for r in host_rows}

    context = {
        "stage": "group",
        "matchday": 1,
        "is_host": home in host_teams,
        "in_host_country": True,
        "group": group,
    }

    try:
        pred = predict_wc_match(home, away, context)
        return {
            "status": "ok",
            "fixture_id": fixture_id,
            "date": str(f["match_date"]),
            "home_team": home,
            "away_team": away,
            "home_score": f["home_score"],
            "away_score": f["away_score"],
            "match_status": f["status"] or "scheduled",
            "prediction": pred,
        }
    except Exception as e:
        return {
            "status": "ok",
            "fixture_id": fixture_id,
            "home_team": home,
            "away_team": away,
            "prediction_error": str(e),
        }


# ============================================================
# Predictions
# ============================================================

@router.get("/predictions")
def get_all_predictions(limit: int = Query(72, ge=1, le=200)):
    """Get predictions for all WC2026 group matches."""
    rows = query("""
        SELECT id, match_date, home_team, away_team
        FROM fixtures
        WHERE league_code = 'WC2026' AND status = 'scheduled'
        ORDER BY match_date ASC, id ASC
        LIMIT %s
    """, [limit], db="football_pred")

    # Get host teams
    host_rows = query("SELECT team FROM wc_groups WHERE is_host = 1", db="football_pred")
    host_teams = {r["team"] for r in host_rows}

    predictions = []
    for f in rows:
        home, away = f["home_team"], f["away_team"]
        try:
            pred = predict_wc_match(home, away, {
                "stage": "group", "matchday": 1,
                "is_host": home in host_teams,
                "in_host_country": True,
            })
            predictions.append({
                "fixture_id": f["id"],
                "date": str(f["match_date"]),
                "home": home, "away": away,
                "wdl": pred["wdl"],
                "expected_goals": pred["expected_goals"],
                "most_likely_score": pred["most_likely_score"],
            })
        except Exception as e:
            predictions.append({
                "fixture_id": f["id"],
                "date": str(f["match_date"]),
                "home": home, "away": away,
                "error": str(e),
            })

    return {"status": "ok", "count": len(predictions), "predictions": predictions}


@router.post("/predict")
def predict_custom(req: PredictRequest):
    """Predict a custom WC matchup."""
    try:
        pred = predict_wc_match(req.home_team, req.away_team, {
            "stage": req.stage,
            "matchday": req.matchday,
            "is_host": req.is_host,
            "in_host_country": True,
        })
        return {"status": "ok", **pred}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# Simulation
# ============================================================

@router.post("/knockout")
def simulate_knockout(req: KnockoutRequest):
    """Simulate knockout bracket from R32 to Final."""
    n_sims = min(max(req.n_sims, 10), 1000)
    try:
        result = simulate_bracket_n_times(n_sims)
        return {"status": "ok", "n_simulations": n_sims, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/golden-ball")
def get_golden_ball():
    """Get Golden Ball candidates."""
    try:
        candidates = get_golden_ball_candidates()
        return {"status": "ok", "candidates": candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upset-alerts")
def get_upset_alerts():
    """Get group stage upset alerts and tanking scenarios."""
    try:
        result = analyze_group_upsets()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate")
def run_simulation(req: SimulateRequest):
    """Run full tournament Monte Carlo simulation."""
    global _simulation_result, _simulation_time

    n_sims = min(max(req.n_sims, 100), 5000)

    try:
        start = time.time()
        _simulation_result = simulate_tournament(n_sims=n_sims)
        _simulation_time = time.time() - start

        return {
            "status": "ok",
            "n_simulations": n_sims,
            "duration_seconds": round(_simulation_time, 1),
            "result": _simulation_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulate/result")
def get_simulation_result():
    """Get the latest simulation result."""
    if _simulation_result is None:
        return {
            "status": "no_data",
            "message": "No simulation has been run yet. POST /worldcup/simulate first.",
        }

    return {
        "status": "ok",
        "n_simulations": _simulation_result["n_simulations"],
        "duration_seconds": round(_simulation_time, 1) if _simulation_time else None,
        "result": _simulation_result,
    }


# ============================================================
# Rankings
# ============================================================

@router.get("/rankings")
def get_rankings():
    """Get all 48 WC teams ranked by official FIFA Elo rating."""
    global _rankings_cache, _rankings_time

    # Cache for 1 hour
    if _rankings_cache and _rankings_time and (time.time() - _rankings_time < 3600):
        return _rankings_cache

    try:
        # Get all WC teams with official data
        rows = query(
            "SELECT team, fifa_ranking, elo_rating, is_host FROM wc_groups ORDER BY elo_rating DESC",
            db="football_pred"
        )
        
        rankings = []
        for i, r in enumerate(rows, 1):
            team = r['team']
            elo = r['elo_rating']
            # Convert Elo to quality scores (calibrated)
            starting_xi = 50 + (elo - 1350) / 11.2
            attack_quality = starting_xi + 2  # Slightly higher for attack
            defense_quality = starting_xi - 2  # Slightly lower for defense
            elo_bonus = (elo - 1650) / 10.0
            
            rankings.append({
                "rank": i,
                "team": team,
                "fifa_ranking": r['fifa_ranking'],
                "elo_rating": elo,
                "is_host": bool(r['is_host']),
                "starting_xi": round(starting_xi, 1),
                "attack_quality": round(attack_quality, 1),
                "defense_quality": round(defense_quality, 1),
                "elo_bonus": round(elo_bonus, 1),
                "top_players": [],
            })

        result = {
            "status": "ok",
            "count": len(rankings),
            "rankings": rankings,
        }

        _rankings_cache = result
        _rankings_time = time.time()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
