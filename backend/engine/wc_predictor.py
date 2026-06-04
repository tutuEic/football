# -*- coding: utf-8 -*-
"""
World Cup Prediction Engine v3 — Ensemble Model
================================================
Combines:
1. Bayesian Dixon-Coles (trained on 10,436 international matches)
2. Poisson Regression (23 features)
3. Elo-Poisson (cold-start friendly)
4. Stacking meta-learner (63.6% accuracy)

Unified entry point for WC predictions.
"""
import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_ensemble import get_ensemble, predict_wc_match as ensemble_predict
from engine.wc_elo_adapter import analyze_squad_elo, clear_elo_cache
from engine.wc_dc_international import normalize_team

# Cache
_prediction_cache = {}
_CACHE_TTL = 300  # 5 min


def clear_all_caches():
    """Clear all caches."""
    global _prediction_cache
    _prediction_cache = {}
    clear_elo_cache()


def predict_wc_match(home_team, away_team, context=None):
    """
    Main prediction entry point.
    
    Args:
        home_team: FIFA country name (e.g., "France")
        away_team: FIFA country name (e.g., "Brazil")
        context: dict with keys:
            - stage: "group", "r16", "qf", "sf", "final"
            - matchday: 1, 2, 3
            - is_host: bool
            - in_host_country: bool
    
    Returns:
        Full prediction dict with probabilities, expected goals,
        score distribution, and all factor breakdowns.
    """
    if context is None:
        context = {"stage": "group", "matchday": 1, "is_host": False, "in_host_country": True}
    
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)
    
    # Check cache
    cache_key = f"{home_team}_{away_team}_{context.get('stage','group')}"
    if cache_key in _prediction_cache:
        ts, data = _prediction_cache[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return data
    
    # Get ensemble prediction
    ensemble = get_ensemble()
    pred = ensemble.predict(home_team, away_team, context)
    
    # Get squad analysis for additional info
    try:
        analysis_h = analyze_squad_elo(home_team)
    except:
        analysis_h = {'top_players': [], 'elo_bonus': 0}
    
    try:
        analysis_a = analyze_squad_elo(away_team)
    except:
        analysis_a = {'top_players': [], 'elo_bonus': 0}
    
    # Build full response
    wdl = pred['wdl']
    xg = pred['expected_goals']
    
    # Apply stage adjustments
    stage = context.get('stage', 'group')
    stage_adjustments = {
        'group': {'goal_mult': 1.0, 'draw_shift': 0.0},
        'r16':   {'goal_mult': 0.92, 'draw_shift': 0.02},
        'qf':    {'goal_mult': 0.90, 'draw_shift': 0.03},
        'sf':    {'goal_mult': 0.88, 'draw_shift': 0.04},
        'final': {'goal_mult': 0.85, 'draw_shift': 0.05},
    }
    adj = stage_adjustments.get(stage, stage_adjustments['group'])
    
    if adj['draw_shift'] != 0:
        total_non_draw = wdl['home_win'] + wdl['away_win']
        if total_non_draw > 0:
            new_draw = min(max(wdl['draw'] + adj['draw_shift'], 0.05), 0.50)
            actual_shift = new_draw - wdl['draw']
            scale = (total_non_draw - actual_shift) / total_non_draw if total_non_draw > 0 else 1
            wdl['home_win'] = round(max(wdl['home_win'] * scale, 0.01), 4)
            wdl['away_win'] = round(max(wdl['away_win'] * scale, 0.01), 4)
            wdl['draw'] = round(new_draw, 4)
    
    result = {
        'home_team': home_team,
        'away_team': away_team,
        'stage': stage,
        'matchday': context.get('matchday', 1),
        'model_version': 'wc_v3_ensemble',
        
        'wdl': wdl,
        'expected_goals': xg,
        'most_likely_score': _estimate_score(wdl, xg),
        'confidence': _calc_confidence(wdl),
        
        'player_analysis': {
            'home': {
                'top_players': analysis_h.get('top_players', [])[:5],
                'elo_bonus': analysis_h.get('elo_bonus', 0),
            },
            'away': {
                'top_players': analysis_a.get('top_players', [])[:5],
                'elo_bonus': analysis_a.get('elo_bonus', 0),
            },
        },
        
        'models': pred.get('models', {}),
        'method': pred.get('method', 'unknown'),
        'weights': pred.get('weights', {}),
    }
    
    _prediction_cache[cache_key] = (time.time(), result)
    return result


def _estimate_score(wdl, xg):
    """Estimate most likely score from WDL and xG."""
    home_xg = xg['home']
    away_xg = xg['away']
    
    # Simple Poisson-based estimate
    from scipy.stats import poisson
    best_prob = 0
    best_score = (1, 0)
    
    for i in range(5):
        for j in range(5):
            p = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
            if p > best_prob:
                best_prob = p
                best_score = (i, j)
    
    return f"{best_score[0]}-{best_score[1]}"


def _calc_confidence(wdl):
    """Calculate prediction confidence (0-1)."""
    max_prob = max(wdl['home_win'], wdl['draw'], wdl['away_win'])
    # Higher max prob = higher confidence
    return round(min((max_prob - 0.33) / 0.50, 1.0), 2)


def predict_match_from_fixture(fixture_id):
    """Predict a match from the fixtures table."""
    rows = query(
        "SELECT * FROM fixtures WHERE id = %s AND league_code = 'WC2026'",
        [fixture_id], db="football_pred"
    )
    if not rows:
        raise ValueError(f"Fixture {fixture_id} not found")
    
    f = rows[0]
    home = f["home_team"]
    away = f["away_team"]
    
    # Determine context
    group_rows = query(
        "SELECT group_name FROM wc_groups WHERE team = %s",
        [home], db="football_pred"
    )
    group = group_rows[0]["group_name"] if group_rows else None
    
    host_rows = query(
        "SELECT team FROM wc_groups WHERE is_host = 1", db="football_pred"
    )
    host_teams = {r["team"] for r in host_rows}
    
    context = {
        "stage": "group",
        "matchday": 1,
        "is_host": home in host_teams,
        "in_host_country": True,
        "group": group,
    }
    
    return predict_wc_match(home, away, context)


def predict_all_group_matches():
    """Predict all WC2026 group stage matches."""
    rows = query(
        "SELECT * FROM fixtures WHERE league_code = 'WC2026' ORDER BY match_date, id",
        db="football_pred"
    )
    
    host_rows = query(
        "SELECT team FROM wc_groups WHERE is_host = 1", db="football_pred"
    )
    host_teams = {r["team"] for r in host_rows}
    
    group_map = {}
    group_rows = query("SELECT team, group_name FROM wc_groups", db="football_pred")
    for r in group_rows:
        group_map[r["team"]] = r["group_name"]
    
    predictions = []
    for f in rows:
        home = f["home_team"]
        away = f["away_team"]
        group = group_map.get(home)
        
        context = {
            "stage": "group",
            "matchday": 1,
            "is_host": home in host_teams,
            "in_host_country": True,
            "group": group,
        }
        
        try:
            pred = predict_wc_match(home, away, context)
            pred["fixture_id"] = f["id"]
            pred["match_date"] = str(f["match_date"])
            predictions.append(pred)
        except Exception as e:
            print(f"[WC] Error predicting {home} vs {away}: {e}")
    
    return predictions


if __name__ == '__main__':
    print("=" * 60)
    print("WC Prediction Engine v3 (Ensemble)")
    print("=" * 60)
    
    tests = [
        ('Brazil', 'Croatia'), ('France', 'Morocco'),
        ('Argentina', 'Saudi Arabia'), ('England', 'Iran'),
        ('Germany', 'Japan'), ('Spain', 'Italy'),
        ('France', 'Brazil'), ('Argentina', 'France'),
    ]
    
    for home, away in tests:
        pred = predict_wc_match(home, away)
        wdl = pred['wdl']
        xg = pred['expected_goals']
        print(f"\n{home} vs {away}")
        print(f"  WDL: {wdl['home_win']:.1%} / {wdl['draw']:.1%} / {wdl['away_win']:.1%}")
        print(f"  xG:  {xg['home']:.2f} - {xg['away']:.2f}")
        print(f"  Score: {pred['most_likely_score']}")
        print(f"  Method: {pred['method']}")
        print(f"  Confidence: {pred['confidence']}")
