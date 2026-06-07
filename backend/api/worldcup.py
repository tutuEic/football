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
import sys, os, time, math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query
from engine.wc_data import analyze_squad
from engine.wc_predictor import predict_wc_match
from engine.wc_simulator import simulate_tournament, load_groups
from engine.wc_knockout import simulate_bracket_n_times, get_golden_ball_candidates, analyze_group_upsets

router = APIRouter(prefix="/worldcup")

# Simulation results are stored in the database so they survive
# multi-worker deployments and server restarts.
_RANKINGS_CACHE = None
_RANKINGS_TIME = None



def _ensure_sim_table():
    """Create the simulation results table if it doesn't exist."""
    from data.mysql_client import execute
    execute("""
        CREATE TABLE IF NOT EXISTS wc_simulation_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            result_json LONGTEXT NOT NULL,
            n_simulations INT NOT NULL,
            duration_seconds FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """, db="football_pred")

def _save_simulation_result(result, n_sims, duration):
    """Persist simulation result to DB (visible to all workers)."""
    import json
    _ensure_sim_table()
    from data.mysql_client import execute
    execute(
        "INSERT INTO wc_simulation_results (result_json, n_simulations, duration_seconds) VALUES (%s, %s, %s)",
        [json.dumps(result, ensure_ascii=False), n_sims, round(duration, 1)],
        db="football_pred",
    )

def _load_simulation_result():
    """Load the most recent simulation result from DB."""
    import json
    _ensure_sim_table()
    rows = query(
        "SELECT result_json, n_simulations, duration_seconds, created_at FROM wc_simulation_results ORDER BY id DESC LIMIT 1",
        db="football_pred",
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "result": json.loads(r["result_json"]),
        "n_simulations": r["n_simulations"],
        "duration_seconds": r["duration_seconds"],
        "created_at": str(r["created_at"]),
    }

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


@router.post("/predict-custom")
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


@router.get("/bracket")
def get_bracket():
    """Fast bracket: group stage qualified teams + knockout predictions."""
    try:
        from engine.wc_knockout import get_wc_groups, simulate_group_stage, _build_r32_matches
        from engine.wc_predictor import predict_wc_match

        groups = get_wc_groups()
        qualified, standings = simulate_group_stage(groups)

        # Build group qualification data
        group_data = {}
        for q in qualified:
            g = q["group"]
            if g not in group_data:
                group_data[g] = {"group": g, "teams": []}
            group_data[g]["teams"].append({
                "team": q["team"],
                "rank": q["rank"],
                "points": q.get("points", 0),
                "gf": q.get("gf", 0),
                "ga": q.get("ga", 0),
            })

        r32_pairs = _build_r32_matches(qualified)

        def predict_match(home, away, stage):
            pred = predict_wc_match(home, away, {"stage": stage, "matchday": 1, "is_host": False})
            wdl = pred["wdl"]
            winner = home if wdl["home_win"] >= wdl["away_win"] else away
            return {"home": home, "away": away, "winner": winner,
                    "wdl": wdl, "xg": pred["expected_goals"]}

        # R32
        r32_results = [predict_match(h, a, "r32") for h, a in r32_pairs]
        r32_winners = [m["winner"] for m in r32_results]

        # R16
        r16_results = [predict_match(r32_winners[i], r32_winners[i+1], "r16") for i in range(0, len(r32_winners)-1, 2)]
        r16_winners = [m["winner"] for m in r16_results]

        # QF
        qf_results = [predict_match(r16_winners[i], r16_winners[i+1], "qf") for i in range(0, len(r16_winners)-1, 2)]
        qf_winners = [m["winner"] for m in qf_results]

        # SF
        sf_results = [predict_match(qf_winners[i], qf_winners[i+1], "sf") for i in range(0, len(qf_winners)-1, 2)]
        sf_winners = [m["winner"] for m in sf_results]

        # Final
        final_results = []
        champion = None
        sf_losers = []
        if len(sf_results) >= 2:
            sf_losers = [m["home"] if m["winner"] == m["away"] else m["away"] for m in sf_results]
        if len(sf_winners) >= 2:
            final_results = [predict_match(sf_winners[0], sf_winners[1], "final")]
            champion = final_results[0]["winner"]

        # Third-place match (SF losers)
        third_results = []
        if len(sf_losers) >= 2:
            third_results = [predict_match(sf_losers[0], sf_losers[1], "third_place")]

        bracket = {
            "groups": [group_data[g] for g in sorted(group_data.keys())],
            "r32": r32_results, "r16": r16_results, "qf": qf_results,
            "sf": sf_results, "final": final_results, "third": third_results,
            "champion": champion
        }
        return {"status": "ok", "bracket": bracket}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/squad/{team_name}")
def get_wc_squad(team_name: str):
    """Get national team squad with player details for sandbox."""
    try:
        analysis = analyze_squad(team_name)
        squad = analysis.get("squad", [])
        # Format players for frontend
        players = []
        for p in squad:
            # Compute detailed ratings from ELO and position
            elo = p.get("strength", 0) or 0
            pos_cat = p.get("pos_category", "MF")
            g90 = p.get("goals_per_90", 0) or 0
            a90 = p.get("assists_per_90", 0) or 0
            total_goals = p.get("total_goals", 0) or p.get("goals", 0) or 0
            total_apps = p.get("total_apps", 0) or 0
            total_mins = p.get("total_mins", 0) or p.get("minutes", 0) or 0

            # Attack rating: weighted by position and goal contribution
            if pos_cat == "FW":
                attack = min(99, elo * 0.6 + g90 * 30 + a90 * 10)
            elif pos_cat == "MF":
                attack = min(99, elo * 0.4 + g90 * 25 + a90 * 15)
            elif pos_cat == "DF":
                attack = min(99, elo * 0.2 + g90 * 20 + a90 * 10)
            else:
                attack = min(99, elo * 0.1 + g90 * 10)

            # Defense rating: weighted by position
            if pos_cat == "GK":
                defense = min(99, elo * 0.8)
            elif pos_cat == "DF":
                defense = min(99, elo * 0.7)
            elif pos_cat == "MF":
                defense = min(99, elo * 0.4)
            else:
                defense = min(99, elo * 0.2)

            # Goal expectation per match (based on position and scoring rate)
            pos_goal_weight = {"FW": 0.8, "MF": 0.3, "DF": 0.05, "GK": 0.005}
            goal_exp = round(g90 * pos_goal_weight.get(pos_cat, 0.2), 3)

            # Overall rating (same as ELO/strength)
            overall = round(elo, 1)

            # Classify player role
            role_key, role_cn, _, _ = classify_player_role(p)

            players.append({
                "player_id": p.get("player_id"),
                "name": p.get("name", ""),
                "position": p.get("position", ""),
                "sub_position": p.get("sub_position", ""),
                "pos_category": pos_cat,
                "club": p.get("current_club_name", ""),
                "league": p.get("league", ""),
                "market_value": p.get("market_value", 0),
                "strength": overall,
                "elo": round(p.get("elo", 0), 1),
                "jersey_number": p.get("jersey_number"),
                "age": p.get("age"),
                "goals": total_goals,
                "assists": p.get("total_assists", 0) or p.get("assists", 0) or 0,
                "minutes": total_mins,
                "apps": total_apps,
                "goals_per_90": round(g90, 2),
                "assists_per_90": round(a90, 2),
                "attack_rating": round(attack, 1),
                "defense_rating": round(defense, 1),
                "goal_expectation": goal_exp,
                "role": role_key,
                "role_cn": role_cn,
            })
        return {
            "status": "ok",
            "team": team_name,
            "analysis": {
                "starting_xi": analysis["starting_xi"],
                "attack_quality": analysis["attack_quality"],
                "defense_quality": analysis["defense_quality"],
                "elo_bonus": analysis["elo_bonus"],
                "avg_age": analysis["avg_age"],
                "squad_size": len(players),
            },
            "players": players,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class WCPredictRequest(BaseModel):
    home_team: str
    away_team: str
    home_lineup: Optional[list] = None
    away_lineup: Optional[list] = None
    n_sims: int = 1000


@router.post("/predict")
def predict_wc_custom(req: WCPredictRequest):
    """Predict WC match with full player integration: roles, chemistry, ratings."""
    try:
        import numpy as np

        context = {"stage": "knockout", "matchday": 1, "is_host": False, "in_host_country": True}

        home_analysis = analyze_squad(req.home_team)
        away_analysis = analyze_squad(req.away_team)
        home_squad = home_analysis.get("squad", [])
        away_squad = away_analysis.get("squad", [])

        # Select lineups
        h_selected = [p for p in home_squad if p.get("player_id") in req.home_lineup] if req.home_lineup else []
        a_selected = [p for p in away_squad if p.get("player_id") in req.away_lineup] if req.away_lineup else []

        # Classify roles and compute chemistry
        h_chemistry, h_roles = _calc_chemistry(h_selected) if h_selected else (0, [])
        a_chemistry, a_roles = _calc_chemistry(a_selected) if a_selected else (0, [])

        # Compute granular adjustments from player data
        h_attack_adj, h_defense_adj = _compute_lineup_adjustments(h_selected, home_analysis)
        a_attack_adj, a_defense_adj = _compute_lineup_adjustments(a_selected, away_analysis)

        # Set piece strength (from analyze_squad, includes height+GK+scorer)
        h_setpiece = home_analysis.get("set_piece_strength", 0.5)
        a_setpiece = away_analysis.get("set_piece_strength", 0.5)
        # Set piece bonus: difference translates to xG boost (max +0.15)
        sp_diff = (h_setpiece - a_setpiece) * 0.15
        h_sp_bonus = max(0, sp_diff)  # home benefits if better at set pieces
        a_sp_bonus = max(0, -sp_diff)  # away benefits if better

        # Base prediction from ensemble
        pred = predict_wc_match(req.home_team, req.away_team, context)
        base_lam = pred["expected_goals"]["home"]
        base_mu = pred["expected_goals"]["away"]

        # Apply all adjustments
        lam = base_lam * h_attack_adj * (1 - a_defense_adj * 0.3) * (1 + h_chemistry) + h_sp_bonus
        mu = base_mu * a_attack_adj * (1 - h_defense_adj * 0.3) * (1 + a_chemistry) + a_sp_bonus

        # Ensure minimum xG
        lam = max(lam, 0.3)
        mu = max(mu, 0.3)

        pred["expected_goals"]["home"] = round(lam, 2)
        pred["expected_goals"]["away"] = round(mu, 2)

        # Score distribution via Monte Carlo with event tracking
        n_sims = min(max(req.n_sims, 100), 5000)
        home_goals_dist = np.random.poisson(max(lam, 0.05), n_sims)
        away_goals_dist = np.random.poisson(max(mu, 0.05), n_sims)

        score_counts = {}
        home_wins, draws, away_wins = 0, 0, 0
        total_goals_list = []
        # Event tracking
        home_dominant = 0  # home wins by 2+ goals
        away_dominant = 0
        comeback_home = 0  # simulations where away leads but home wins
        comeback_away = 0
        late_goals = 0  # simulations with goals in 75+ min (simulated)
        clean_sheet_home = 0
        clean_sheet_away = 0
        high_scoring = 0  # 4+ total goals
        low_scoring = 0   # 0-1 total goals

        for hg, ag in zip(home_goals_dist, away_goals_dist):
            key = f"{hg}-{ag}"
            score_counts[key] = score_counts.get(key, 0) + 1
            total_goals_list.append(hg + ag)
            if hg > ag:
                home_wins += 1
                if hg - ag >= 2: home_dominant += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1
                if ag - hg >= 2: away_dominant += 1
            if hg == 0: clean_sheet_away += 1
            if ag == 0: clean_sheet_home += 1
            if hg + ag >= 4: high_scoring += 1
            if hg + ag <= 1: low_scoring += 1

        # Top scores
        top_scores = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        score_dist = [{"score": s, "prob": round(c / n_sims, 4)} for s, c in top_scores]

        # Over/under
        over25 = sum(1 for g in total_goals_list if g > 2.5) / n_sims
        over15 = sum(1 for g in total_goals_list if g > 1.5) / n_sims
        over35 = sum(1 for g in total_goals_list if g > 3.5) / n_sims
        btts = sum(1 for hg, ag in zip(home_goals_dist, away_goals_dist) if hg > 0 and ag > 0) / n_sims

        # Goal scorer predictions
        home_scorers = _predict_scorers(home_squad, req.home_lineup, lam, "home")
        away_scorers = _predict_scorers(away_squad, req.away_lineup, mu, "away")

        # Effective ratios (attack_adj already includes chemistry)
        h_ratio = h_attack_adj * (1 + h_chemistry)
        a_ratio = a_attack_adj * (1 + a_chemistry)

        # Key factors based on SIMULATION EVENTS
        factors = _build_event_factors(
            req.home_team, req.away_team, home_analysis, away_analysis,
            home_squad, away_squad, h_ratio, a_ratio,
            n_sims, home_wins, draws, away_wins,
            home_dominant, away_dominant,
            clean_sheet_home, clean_sheet_away,
            high_scoring, low_scoring, lam, mu,
            home_goals_dist, away_goals_dist, home_scorers, away_scorers
        )

        return {
            "status": "ok",
            "wdl": {
                "home_win": round(home_wins / n_sims, 4),
                "draw": round(draws / n_sims, 4),
                "away_win": round(away_wins / n_sims, 4),
            },
            "expected_goals": pred["expected_goals"],
            "score_distribution": score_dist,
            "over_under": {
                "over_1_5": round(over15, 4),
                "over_2_5": round(over25, 4),
                "over_3_5": round(over35, 4),
                "btts": round(btts, 4),
            },
            "goal_scorers": {
                "home": home_scorers[:8],
                "away": away_scorers[:8],
            },
            "key_factors": factors,
            "n_simulations": n_sims,
            "home_xi": round(home_analysis["starting_xi"] * h_ratio, 1),
            "away_xi": round(away_analysis["starting_xi"] * a_ratio, 1),
            "home_chemistry": round(h_chemistry * 100, 1),
            "away_chemistry": round(a_chemistry * 100, 1),
            "home_setpiece": round(h_setpiece * 100, 1),
            "away_setpiece": round(a_setpiece * 100, 1),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _predict_scorers(squad, lineup, expected_goals, side):
    """Predict goal scorer probabilities based on player strength and position."""
    if not squad:
        return []

    # Filter to lineup if provided, otherwise use top players
    if lineup:
        players = [p for p in squad if p.get("player_id") in lineup]
    else:
        players = sorted(squad, key=lambda p: p.get("strength", 0), reverse=True)[:11]

    if not players:
        return []

    # Weight by position (FW > MF > DF > GK) and strength
    pos_weight = {"FW": 3.0, "MF": 1.5, "DF": 0.3, "GK": 0.05}
    weighted = []
    for p in players:
        cat = p.get("pos_category", "MF")
        strength = p.get("strength", 50)
        w = pos_weight.get(cat, 1.0) * (strength / 60.0)
        # Boost for players with high goals_per_90
        g90 = p.get("goals_per_90", 0) or 0
        w *= (1 + g90 * 2)
        weighted.append((p, max(w, 0.01)))

    total_w = sum(w for _, w in weighted)
    scorers = []
    for p, w in weighted:
        # Probability of scoring at least one goal
        # P(score) ≈ 1 - exp(-lambda * player_share)
        player_share = w / total_w
        lam_player = expected_goals * player_share
        p_score = 1 - math.exp(-max(lam_player, 0.001))
        if p_score > 0.01:
            scorers.append({
                "name": p.get("name", ""),
                "position": p.get("position", ""),
                "elo": round(p.get("strength", 0), 1),
                "prob_anytime": round(p_score, 3),
                "goals_per_90": round(p.get("goals_per_90", 0) or 0, 2),
            })

    scorers.sort(key=lambda x: x["prob_anytime"], reverse=True)
    return scorers


def _compute_lineup_adjustments(selected, analysis):
    """
    Compute attack and defense multipliers from lineup player data.
    Returns (attack_multiplier, defense_quality).
    
    Attack multiplier: based on avg attack_rating of FW/MF vs team default
    Defense quality: based on avg defense_rating of DF/GK (0-1 scale, used to reduce opponent xG)
    """
    if not selected:
        return 1.0, 0.0

    # Attack: average attack_rating of attacking players
    attackers = [p for p in selected if p.get("pos_category") in ("FW", "MF")]
    if attackers:
        avg_attack = sum(p.get("attack_rating", 50) for p in attackers) / len(attackers)
        # Compare to a baseline (60 = average team)
        attack_adj = avg_attack / 60.0
        attack_adj = max(0.7, min(attack_adj, 1.4))  # Clamp 0.7-1.4
    else:
        attack_adj = 1.0

    # Defense: average defense_rating of defensive players
    defenders = [p for p in selected if p.get("pos_category") in ("DF", "GK")]
    if defenders:
        avg_defense = sum(p.get("defense_rating", 50) for p in defenders) / len(defenders)
        # Normalize to 0-1 scale (50 = weak, 80 = strong)
        defense_quality = max(0, min((avg_defense - 40) / 50, 1.0))
    else:
        defense_quality = 0.0

    return attack_adj, defense_quality


def classify_player_role(p):
    """
    Classify a player into a specific role based on stats and position.
    Returns (role_name, role_cn, bonus_type, bonus_value).
    
    GK roles:
      - 门神 (shot-stopper): high ELO, low goals conceded
      - 出击型 (sweeper-keeper): high ELO + decent assists
    
    DF roles:
      - 铁卫 (stopper): high ELO, low attack contribution
      - 带刀后卫 (ball-playing CB): decent goals + assists
      - 攻击型边卫 (attacking full-back): high assists
    
    MF roles:
      - 节拍器 (controller/tempo): good ELO + balanced goals/assists
      - 组织核心 (playmaker): high assists
      - 绞肉机 (destroyer): high ELO, low attack, defensive MF
      - B2B (box-to-box): good goals + assists + high ELO
      - 前腰 (CAM): high goals + assists
    
    FW roles:
      - 射手 (poacher): very high goals, low assists
      - 全能前锋 (complete forward): good goals + assists
      - 边锋 (winger): high assists + decent goals
      - 支点 (target man): high strength, lower goals
    """
    cat = p.get("pos_category", "MF")
    g90 = p.get("goals_per_90", 0) or 0
    a90 = p.get("assists_per_90", 0) or 0
    elo = p.get("strength", 0) or 0
    pos = (p.get("position") or "").lower()
    sub = (p.get("sub_position") or "").lower()

    if cat == "GK":
        if elo > 65:
            return "shot_stopper", "门神", "defense", 0.03
        return "goalkeeper", "门将", "none", 0

    if cat == "DF":
        is_fullback = "back" in sub or "wing-back" in sub or "back" in pos
        if is_fullback and a90 > 0.12 and elo > 60:
            return "attacking_fb", "攻击型边卫", "attack", 0.02
        if g90 > 0.08 and a90 > 0.05 and elo > 60:
            return "ball_playing_cb", "带刀后卫", "attack", 0.015
        if elo > 63:
            return "stopper", "铁卫", "defense", 0.02
        return "defender", "后卫", "none", 0

    if cat == "MF":
        is_defensive = "defensive" in sub or "defens" in pos or "holding" in sub
        is_attacking = "attack" in sub or "attack" in pos or "cam" in sub

        # Attacking midfielder (CAM)
        if is_attacking and g90 > 0.20 and a90 > 0.15 and elo > 63:
            return "cam", "前腰", "attack", 0.03
        # Playmaker
        if a90 > 0.30 and elo > 65:
            return "playmaker", "组织核心", "control", 0.04
        # B2B
        if g90 > 0.15 and a90 > 0.10 and elo > 63:
            return "b2b", "B2B", "allround", 0.025
        # Destroyer
        if is_defensive and elo > 63 and g90 < 0.10:
            return "destroyer", "绞肉机", "defense", 0.02
        # Controller
        if elo > 60 and g90 > 0.10 and a90 > 0.05:
            return "controller", "节拍器", "control", 0.02
        return "midfielder", "中场", "none", 0

    if cat == "FW":
        is_winger = "winger" in sub or "wing" in pos
        if is_winger and a90 > 0.20 and elo > 63:
            return "winger", "边锋", "attack", 0.025
        if g90 > 0.50 and a90 < 0.15:
            return "poacher", "射手", "attack", 0.03
        if g90 > 0.30 and a90 > 0.15 and elo > 65:
            return "complete_fw", "全能前锋", "attack", 0.035
        if elo > 60 and g90 > 0.15:
            return "forward", "前锋", "attack", 0.01
        return "striker", "中锋", "none", 0

    return "player", "球员", "none", 0


def _calc_chemistry(selected):
    """
    Calculate team chemistry from classified player roles.
    Different role combinations create synergy bonuses.
    """
    if not selected:
        return 0, []

    roles = []
    for p in selected:
        role_key, role_cn, bonus_type, bonus_val = classify_player_role(p)
        roles.append({
            "name": p.get("name", ""),
            "role": role_key,
            "role_cn": role_cn,
            "bonus_type": bonus_type,
            "bonus_val": bonus_val,
            "elo": p.get("strength", 0) or 0,
        })

    # Only count top 6 contributors (not every player)
    top_contributors = sorted([r for r in roles if r["bonus_val"] > 0],
                              key=lambda r: r["bonus_val"] * (r["elo"] / 100),
                              reverse=True)[:6]

    total = 0
    for r in top_contributors:
        elo_factor = max(0, (r["elo"] - 50) / 50)
        total += r["bonus_val"] * elo_factor

    # Synergy: specific role combinations
    role_keys = [r["role"] for r in roles]

    # Playmaker + B2B = midfield dominance
    if "playmaker" in role_keys and "b2b" in role_keys:
        total += 0.02
    # Playmaker + CAM = creative overload
    if "playmaker" in role_keys and "cam" in role_keys:
        total += 0.02
    # Controller + destroyer = balanced midfield
    if "controller" in role_keys and "destroyer" in role_keys:
        total += 0.015
    # Poacher + winger = classic combo
    if "poacher" in role_keys and "winger" in role_keys:
        total += 0.02
    # Complete forward + playmaker = versatile attack
    if "complete_fw" in role_keys and "playmaker" in role_keys:
        total += 0.02
    # Shot-stopper + stopper = defensive wall
    if "shot_stopper" in role_keys and "stopper" in role_keys:
        total += 0.015
    # Multiple elite roles (3+ key players)
    key_count = sum(1 for r in roles if r["bonus_val"] >= 0.025)
    if key_count >= 4:
        total *= 1.25
    elif key_count >= 3:
        total *= 1.15

    return min(total, 0.15), roles


def _build_event_factors(home_team, away_team, home_analysis, away_analysis,
                         home_squad, away_squad, h_ratio, a_ratio,
                         n_sims, home_wins, draws, away_wins,
                         home_dominant, away_dominant,
                         clean_sheet_home, clean_sheet_away,
                         high_scoring, low_scoring, lam, mu,
                         home_goals_dist, away_goals_dist, home_scorers, away_scorers):
    """Build key factors based on actual simulation events."""
    factors = []

    # 1. Win probability dominance
    win_diff = abs(home_wins - away_wins) / n_sims
    if win_diff > 0.15:
        better = home_team if home_wins > away_wins else away_team
        pct = max(home_wins, away_wins) / n_sims * 100
        factors.append({"factor": "胜率优势", "impact": "high" if win_diff > 0.25 else "medium",
                        "description": f"模拟{n_sims}场中{better}胜率{pct:.0f}%，明显占优",
                        "direction": "home" if home_wins > away_wins else "away"})

    # 2. Dominant wins (2+ goals)
    dom_pct = max(home_dominant, away_dominant) / n_sims
    if dom_pct > 0.15:
        who = home_team if home_dominant > away_dominant else away_team
        factors.append({"factor": "碾压局", "impact": "high" if dom_pct > 0.25 else "medium",
                        "description": f"{who}有{dom_pct*100:.0f}%的概率净胜2球以上，存在大比分可能",
                        "direction": "home" if home_dominant > away_dominant else "away"})

    # 3. Clean sheet probability
    cs_pct = max(clean_sheet_home, clean_sheet_away) / n_sims
    if cs_pct > 0.25:
        who = home_team if clean_sheet_home > clean_sheet_away else away_team
        factors.append({"factor": "零封能力", "impact": "medium",
                        "description": f"{who}有{cs_pct*100:.0f}%的概率零封对手，防守稳固",
                        "direction": "home" if clean_sheet_home > clean_sheet_away else "away"})

    # 4. High/low scoring tendency
    if high_scoring / n_sims > 0.3:
        factors.append({"factor": "进球大战", "impact": "medium",
                        "description": f"模拟中{high_scoring/n_sims*100:.0f}%的比赛出现4+进球，进攻端活跃",
                        "direction": "home" if lam > mu else "away"})
    elif low_scoring / n_sims > 0.3:
        factors.append({"factor": "防守对决", "impact": "medium",
                        "description": f"模拟中{low_scoring/n_sims*100:.0f}%的比赛仅0-1球，双方防守严密，定位球是关键",
                        "direction": "home" if lam > mu else "away"})

    # 5. Top scorer threat
    if home_scorers:
        top = home_scorers[0]
        if top["prob_anytime"] > 0.35:
            factors.append({"factor": "核心射手", "impact": "high",
                            "description": f"{top['name']}本场进球概率{top['prob_anytime']*100:.0f}%，场均{top['goals_per_90']:.2f}球(ELO {top['elo']:.0f})，是{home_team}最大威胁",
                            "direction": "home"})
        elif top["prob_anytime"] > 0.2:
            factors.append({"factor": "锋线威胁", "impact": "medium",
                            "description": f"{top['name']}进球概率{top['prob_anytime']*100:.0f}%，场均{top['goals_per_90']:.2f}球，需要重点盯防",
                            "direction": "home"})
    if away_scorers:
        top = away_scorers[0]
        if top["prob_anytime"] > 0.35:
            factors.append({"factor": "核心射手", "impact": "high",
                            "description": f"{top['name']}本场进球概率{top['prob_anytime']*100:.0f}%，场均{top['goals_per_90']:.2f}球(ELO {top['elo']:.0f})，是{away_team}最大威胁",
                            "direction": "away"})
        elif top["prob_anytime"] > 0.2:
            factors.append({"factor": "锋线威胁", "impact": "medium",
                            "description": f"{top['name']}进球概率{top['prob_anytime']*100:.0f}%，场均{top['goals_per_90']:.2f}球，需要重点盯防",
                            "direction": "away"})

    # 6. Midfield battle
    if home_squad:
        top_mf = sorted([p for p in home_squad if p.get("pos_category") == "MF"], key=lambda p: p.get("strength", 0), reverse=True)
        if top_mf and top_mf[0].get("strength", 0) > 65:
            p = top_mf[0]
            factors.append({"factor": "中场调度", "impact": "medium",
                            "description": f"{p['name']}(ELO {p.get('strength',0):.0f})掌控{home_team}中场，组织进攻节奏",
                            "direction": "home"})
    if away_squad:
        top_mf = sorted([p for p in away_squad if p.get("pos_category") == "MF"], key=lambda p: p.get("strength", 0), reverse=True)
        if top_mf and top_mf[0].get("strength", 0) > 65:
            p = top_mf[0]
            factors.append({"factor": "中场调度", "impact": "medium",
                            "description": f"{p['name']}(ELO {p.get('strength',0):.0f})掌控{away_team}中场，组织进攻节奏",
                            "direction": "away"})

    # 7. xG comparison insight
    xg_diff = abs(lam - mu)
    if xg_diff > 0.5:
        better = home_team if lam > mu else away_team
        factors.append({"factor": "预期进球差距", "impact": "medium",
                        "description": f"{better}预期进球{max(lam,mu):.2f} vs {min(lam,mu):.2f}，进攻效率差距明显",
                        "direction": "home" if lam > mu else "away"})

    # 8. Draw tendency
    draw_pct = draws / n_sims
    if draw_pct > 0.3:
        factors.append({"factor": "平局倾向", "impact": "medium",
                        "description": f"模拟中{draw_pct*100:.0f}%的比赛以平局收场，双方实力接近，胶着概率高",
                        "direction": "home"})

    # 9. Squad depth
    h_depth = home_analysis.get("squad_depth", 50)
    a_depth = away_analysis.get("squad_depth", 50)
    if abs(h_depth - a_depth) > 5:
        better = home_team if h_depth > a_depth else away_team
        factors.append({"factor": "板凳深度", "impact": "low",
                        "description": f"{better}替补阵容更强({max(h_depth,a_depth):.0f} vs {min(h_depth,a_depth):.0f})，换人调整空间更大",
                        "direction": "home" if h_depth > a_depth else "away"})

    # 10. Age/physical
    h_age = home_analysis.get("avg_age", 25)
    a_age = away_analysis.get("avg_age", 25)
    if abs(h_age - a_age) > 3:
        younger = home_team if h_age < a_age else away_team
        factors.append({"factor": "年龄优势", "impact": "low",
                        "description": f"{younger}平均年龄更小({min(h_age,a_age):.1f} vs {max(h_age,a_age):.1f})，体能和冲击力占优",
                        "direction": "home" if h_age < a_age else "away"})

    # 11. Set piece advantage
    h_sp = home_analysis.get("set_piece_strength", 0.5)
    a_sp = away_analysis.get("set_piece_strength", 0.5)
    sp_diff = abs(h_sp - a_sp)
    if sp_diff > 0.08:
        better = home_team if h_sp > a_sp else away_team
        factors.append({"factor": "定位球优势", "impact": "high" if sp_diff > 0.15 else "medium",
                        "description": f"{better}定位球能力更强({max(h_sp,a_sp)*100:.0f} vs {min(h_sp,a_sp)*100:.0f})，角球和任意球是得分利器",
                        "direction": "home" if h_sp > a_sp else "away"})

    return factors


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
    """Simulation-based upset analysis: run multiple group stages, analyze patterns."""
    try:
        import numpy as np
        from collections import defaultdict, Counter
        from engine.wc_knockout import get_wc_groups, simulate_group_stage, _build_r32_matches
        from engine.wc_predictor import predict_wc_match

        N_SIMS = 100  # Run 100 group stage simulations

        groups = get_wc_groups()
        all_team_data = {}

        # Pre-compute team analysis data
        for group_name, teams in groups.items():
            for t in teams:
                team = t["team"]
                if team not in all_team_data:
                    analysis = analyze_squad(team)
                    all_team_data[team] = {
                        "elo": analysis.get("starting_xi", 50),
                        "attack": analysis.get("attack_quality", 50),
                        "defense": analysis.get("defense_quality", 50),
                        "avg_age": analysis.get("avg_age", 25),
                        "set_piece": analysis.get("set_piece_strength", 0.5),
                        "group": group_name,
                    }

        # Run N simulations and track outcomes
        team_finishes = defaultdict(lambda: {"1st": 0, "2nd": 0, "3rd": 0, "4th": 0})
        team_r32_opponents = defaultdict(lambda: {"as_1st": [], "as_2nd": []})

        for sim_idx in range(N_SIMS):
            qualified, _ = simulate_group_stage(groups)
            r32_pairs = _build_r32_matches(qualified)

            # Ensure all teams in R32 pairs have analysis data
            for h, a in r32_pairs:
                for team in [h, a]:
                    if team and team not in all_team_data:
                        analysis = analyze_squad(team)
                        all_team_data[team] = {
                            "elo": analysis.get("starting_xi", 50),
                            "attack": analysis.get("attack_quality", 50),
                            "defense": analysis.get("defense_quality", 50),
                            "avg_age": analysis.get("avg_age", 25),
                            "set_piece": analysis.get("set_piece_strength", 0.5),
                            "group": "?",
                        }

            # Track group finishes
            for q in qualified:
                rank = q["rank"]
                team_finishes[q["team"]][f"{rank}{['st','nd','rd','th'][rank-1]}"] += 1

            # Track R32 opponents for each team based on their finish
            for q in qualified:
                team = q["team"]
                group = q["group"]
                rank = q["rank"]

                # Find this team's R32 opponent
                for h, a in r32_pairs:
                    if h == team:
                        opp = a
                        if rank == 1:
                            team_r32_opponents[team]["as_1st"].append(opp)
                        elif rank == 2:
                            team_r32_opponents[team]["as_2nd"].append(opp)
                        break
                    elif a == team:
                        opp = h
                        if rank == 1:
                            team_r32_opponents[team]["as_1st"].append(opp)
                        elif rank == 2:
                            team_r32_opponents[team]["as_2nd"].append(opp)
                        break

            # No R32 match simulation needed - tanking analysis is sufficient

        alerts = []

        # 1. TANKING ANALYSIS: Compare R32 opponent ELO when finishing 1st vs 2nd
        for team, data in all_team_data.items():
            as_1st = team_r32_opponents[team]["as_1st"]
            as_2nd = team_r32_opponents[team]["as_2nd"]

            if len(as_1st) < 5 or len(as_2nd) < 5:
                continue

            # Average R32 opponent ELO for each finish position
            avg_opp_1st = np.mean([all_team_data.get(o, {}).get("elo", 50) for o in as_1st])
            avg_opp_2nd = np.mean([all_team_data.get(o, {}).get("elo", 50) for o in as_2nd])

            # How often they finish 1st vs 2nd
            total_sims = len(as_1st) + len(as_2nd)
            pct_1st = len(as_1st) / total_sims
            pct_2nd = len(as_2nd) / total_sims

            # Tanking incentive: 1st place opponent is HARDER than 2nd place opponent
            incentive = avg_opp_1st - avg_opp_2nd

            if incentive > 3:  # 1st place faces harder opponent
                # Factor in team strength - strong teams have more reason to tank
                team_elo = data["elo"]
                # Factor in group consistency - if team always finishes 1st, tanking is deliberate
                consistency = pct_1st  # Higher = more consistent 1st place finisher

                # Combined tanking probability score
                tank_score = incentive * 0.4 + team_elo * 0.01 + consistency * 20

                if tank_score > 5:
                    alerts.append({
                        "type": "tanking_risk",
                        "team": team,
                        "group": data["group"],
                        "impact": "high" if tank_score > 15 else "medium" if tank_score > 10 else "low",
                        "incentive": round(incentive, 1),
                        "elo_1st_opp": round(avg_opp_1st, 1),
                        "elo_2nd_opp": round(avg_opp_2nd, 1),
                        "pct_1st": round(pct_1st * 100, 1),
                        "pct_2nd": round(pct_2nd * 100, 1),
                        "tank_score": round(tank_score, 1),
                        "description": (
                            f"{team}({data['group']}组)第1名R32对手平均ELO {avg_opp_1st:.0f}，"
                            f"第2名对手ELO {avg_opp_2nd:.0f}，差距{incentive:.0f}分。"
                            f"模拟中{pct_1st*100:.0f}%获第1、{pct_2nd*100:.0f}%获第2，"
                            f"放水动机评分{tank_score:.1f}"
                        ),
                    })

        # 2. PENALTY SHOOTOUT ABILITY
        penalty_teams = []
        for team, data in all_team_data.items():
            gk_score = data["defense"] * 0.4
            age_factor = min(max((data["avg_age"] - 24) / 8, 0), 1) * 30
            tech_score = data["attack"] * 0.3
            penalty_ability = gk_score + age_factor + tech_score
            penalty_teams.append({"team": team, "penalty": round(penalty_ability, 1)})

        penalty_teams.sort(key=lambda x: x["penalty"], reverse=True)

        for pt in penalty_teams[:5]:
            alerts.append({
                "type": "penalty_strength",
                "team": pt["team"],
                "penalty_ability": pt["penalty"],
                "impact": "high" if pt["penalty"] > 75 else "medium",
                "description": f"{pt['team']}点球能力强({pt['penalty']:.0f}分)，淘汰赛若进入点球大战占优",
            })

        # Sort alerts by impact
        impact_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda a: (impact_order.get(a.get("impact", "low"), 3),))

        return {"status": "ok", "alerts": alerts, "penalty_ranking": penalty_teams[:10], "n_simulations": N_SIMS}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_bracket_internal():
    """Internal function to get bracket data without HTTP."""
    try:
        from engine.wc_knockout import get_wc_groups, simulate_group_stage, _build_r32_matches
        from engine.wc_predictor import predict_wc_match

        groups = get_wc_groups()
        qualified, _ = simulate_group_stage(groups)
        r32_pairs = _build_r32_matches(qualified)

        def predict_match(home, away, stage):
            pred = predict_wc_match(home, away, {"stage": stage, "matchday": 1, "is_host": False})
            wdl = pred["wdl"]
            winner = home if wdl["home_win"] >= wdl["away_win"] else away
            return {"home": home, "away": away, "winner": winner}

        r32_results = [predict_match(h, a, "r32") for h, a in r32_pairs]
        return {"r32": r32_results}
    except:
        return None


@router.get("/group-analysis/{group_name}")
def get_group_analysis(group_name: str):
    """Get group stage analysis text for a specific group."""
    try:
        rows = query(
            "SELECT analysis_text FROM wc_group_analysis WHERE group_name = %s",
            params=[group_name],
            db='football_pred'
        )
        if rows:
            return {"status": "ok", "group": group_name, "text": rows[0]["analysis_text"]}
        return {"status": "error", "message": f"No analysis found for group {group_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team-analysis/{team_name}")
def get_team_analysis(team_name: str):
    """Generate comprehensive team analysis with qualification predictions and knockout path."""
    try:
        import numpy as np
        from collections import defaultdict
        from engine.wc_knockout import get_wc_groups, simulate_group_stage, _build_r32_matches
        from engine.wc_predictor import predict_wc_match

        N_SIMS = 100
        groups = get_wc_groups()

        # Find team's group
        team_group = None
        group_teams = []
        for gname, gteams in groups.items():
            for t in gteams:
                if t["team"] == team_name:
                    team_group = gname
                    group_teams = [tt["team"] for tt in gteams]
                    break
            if team_group:
                break

        if not team_group:
            return {"status": "error", "message": f"Team '{team_name}' not found"}

        # Get team analysis
        analysis = analyze_squad(team_name)
        squad = analysis.get("squad", [])
        opponents = [t for t in group_teams if t != team_name]

        # Predict matches against each opponent
        match_predictions = []
        for opp in opponents:
            pred = predict_wc_match(team_name, opp, {"stage": "group", "matchday": 1, "is_host": False, "in_host_country": True})
            match_predictions.append({
                "opponent": opp,
                "wdl": pred["wdl"],
                "xg": pred["expected_goals"],
                "most_likely_score": pred.get("most_likely_score", "1-0"),
            })

        # Core players (top 7 by ELO)
        core_players = []
        for p in sorted(squad, key=lambda x: x.get("strength", 0), reverse=True)[:7]:
            core_players.append({
                "name": p.get("name", ""),
                "position": p.get("position", ""),
                "pos_category": p.get("pos_category", ""),
                "club": p.get("current_club_name", ""),
                "elo": round(p.get("strength", 0), 1),
                "age": p.get("age"),
                "goals_per_90": round(p.get("goals_per_90", 0) or 0, 2),
                "assists_per_90": round(p.get("assists_per_90", 0) or 0, 2),
                "market_value": p.get("market_value", 0),
            })

        # Run Monte Carlo simulations for qualification probabilities
        qual_positions = defaultdict(int)  # {position: count}
        knockout_paths = defaultdict(int)  # {opponent: count}
        group_results = []  # Store full group standings per sim

        for _ in range(N_SIMS):
            qualified, _ = simulate_group_stage(groups)
            r32_pairs = _build_r32_matches(qualified)

            # Find this team's position
            for q in qualified:
                if q["team"] == team_name:
                    qual_positions[q["rank"]] += 1

                    # Find R32 opponent (exclude same-group teams)
                    group_set = set(group_teams)
                    for h, a in r32_pairs:
                        if h == team_name and a not in group_set:
                            knockout_paths[a] += 1
                            break
                        elif a == team_name and h not in group_set:
                            knockout_paths[h] += 1
                            break
                    break

        # Calculate qualification probabilities
        total_qualified = sum(qual_positions.values())
        qual_probs = {}
        for pos in [1, 2, 3]:
            qual_probs[pos] = round(qual_positions.get(pos, 0) / N_SIMS * 100, 1)

        total_qualified_pct = round(total_qualified / N_SIMS * 100, 1)

        # Top knockout opponents
        top_opponents = sorted(knockout_paths.items(), key=lambda x: x[1], reverse=True)[:5]
        knockout_analysis = []
        for opp, count in top_opponents:
            opp_analysis = analyze_squad(opp)
            # Get real ELO from wc_groups table
            opp_elo_rows = query("SELECT elo_rating FROM wc_groups WHERE team = %s", params=[opp], db='football_pred')
            real_elo = opp_elo_rows[0]['elo_rating'] if opp_elo_rows else opp_analysis.get('starting_xi', 50) * 18
            knockout_analysis.append({
                "opponent": opp,
                "probability": round(count / total_qualified * 100, 1) if total_qualified > 0 else 0,
                "elo": round(real_elo, 0),
            })

        # Tactical style
        fw_count = sum(1 for p in squad if p.get("pos_category") == "FW")
        mf_count = sum(1 for p in squad if p.get("pos_category") == "MF")
        df_count = sum(1 for p in squad if p.get("pos_category") == "DF")
        avg_age = analysis.get("avg_age", 25)
        attack_q = analysis.get("attack_quality", 50)
        defense_q = analysis.get("defense_quality", 50)

        if attack_q > defense_q + 5:
            style = "进攻型"
            style_desc = f"进攻质量({attack_q:.0f})明显高于防守({defense_q:.0f})，倾向于主动进攻"
        elif defense_q > attack_q + 5:
            style = "防守反击型"
            style_desc = f"防守质量({defense_q:.0f})高于进攻({attack_q:.0f})，倾向于稳固防守后反击"
        else:
            style = "均衡型"
            style_desc = f"攻防均衡(进攻{attack_q:.0f}/防守{defense_q:.0f})，战术灵活"

        # Risk factors
        risks = []
        if avg_age > 28:
            risks.append(f"平均年龄{avg_age:.1f}偏大，高强度比赛体能可能不足")
        if avg_age < 23:
            risks.append(f"平均年龄{avg_age:.1f}偏年轻，大赛经验可能不足")
        if defense_q < 55:
            risks.append(f"防守质量偏低({defense_q:.0f})，面对强队容易失球")
        if attack_q < 55:
            risks.append(f"进攻质量偏低({attack_q:.0f})，破门能力有限")

        # Generate strategic analysis
        strategy = []
        if qual_probs[1] > 50:
            strategy.append(f"{team_name}大概率以小组第1出线({qual_probs[1]}%)，应争取三战全胜锁定头名")
        elif qual_probs[2] > 40:
            strategy.append(f"{team_name}最可能以第2名出线({qual_probs[2]}%)，需确保对弱队全取三分")
        elif total_qualified_pct < 60:
            strategy.append(f"{team_name}出线概率仅{total_qualified_pct}%，每场比赛都至关重要")

        if knockout_analysis:
            likely_opp = knockout_analysis[0]
            strategy.append(f"出线后最可能面对{likely_opp['opponent']}(概率{likely_opp['probability']}%，ELO {likely_opp['elo']:.0f})")

        return {
            "status": "ok",
            "team": team_name,
            "group": team_group,
            "opponents": opponents,
            "analysis": {
                "starting_xi": analysis.get("starting_xi", 50),
                "attack_quality": attack_q,
                "defense_quality": defense_q,
                "avg_age": round(avg_age, 1),
                "squad_depth": analysis.get("squad_depth", 50),
                "set_piece": round(analysis.get("set_piece_strength", 0.5) * 100, 1),
                "elo_bonus": analysis.get("elo_bonus", 0),
            },
            "match_predictions": match_predictions,
            "core_players": core_players,
            "tactical_style": style,
            "style_description": style_desc,
            "formation_tendency": f"{df_count}后卫 {mf_count}中场 {fw_count}前锋",
            "qualification": {
                "total_pct": total_qualified_pct,
                "as_1st": qual_probs.get(1, 0),
                "as_2nd": qual_probs.get(2, 0),
                "as_3rd": qual_probs.get(3, 0),
                "eliminated": round(100 - total_qualified_pct, 1),
            },
            "knockout_path": knockout_analysis,
            "strategy": strategy,
            "risks": risks,
            "squad_size": len(squad),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/simulate")
def run_simulation(req: SimulateRequest):
    """Run full tournament Monte Carlo simulation."""
    n_sims = min(max(req.n_sims, 100), 5000)

    try:
        start = time.time()
        result = simulate_tournament(n_sims=n_sims)
        duration = time.time() - start

        _save_simulation_result(result, n_sims, duration)

        return {
            "status": "ok",
            "n_simulations": n_sims,
            "duration_seconds": round(duration, 1),
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulate/result")
def get_simulation_result():
    """Get the latest simulation result (from DB, works across workers)."""
    stored = _load_simulation_result()
    if stored is None:
        return {
            "status": "no_data",
            "message": "No simulation has been run yet. POST /worldcup/simulate first.",
        }

    return {
        "status": "ok",
        "n_simulations": stored["n_simulations"],
        "duration_seconds": stored["duration_seconds"],
        "created_at": stored["created_at"],
        "result": stored["result"],
    }


# ============================================================
# Rankings
# ============================================================

@router.get("/rankings")
def get_rankings():
    """Get all 48 WC teams ranked by official FIFA Elo rating."""
    global _RANKINGS_CACHE, _RANKINGS_TIME

    # Cache for 1 hour
    if _RANKINGS_CACHE and _RANKINGS_TIME and (time.time() - _RANKINGS_TIME < 3600):
        return _RANKINGS_CACHE

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

        _RANKINGS_CACHE = result
        _RANKINGS_TIME = time.time()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
