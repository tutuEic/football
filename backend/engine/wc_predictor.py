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


# Dixon-Coles rho for internationals (more conservative)
DC_RHO = -0.10         # Negative per Dixon-Coles convention (low-score correlation)

# Knockout: negative rho (fewer draws, more decisive results)
STAGE_RHO = {
    "group":  -0.10,
    "r16":   -0.15,
    "qf":    -0.15,
    "sf":    -0.12,
    "final": -0.10,
    "third":  0.00,
}


def _dc_prob_matrix(lam, mu, rho=None, stage="group", max_goals=8):
    """Compute Dixon-Coles probability matrix with tau correction."""
    if rho is None:
        rho = STAGE_RHO.get(stage, DC_RHO)
    from scipy.stats import poisson

    n = max_goals + 1
    prob = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
            if i == 0 and j == 0:
                tau = max(1 - lam * mu * rho, 1e-10)
            elif i == 0 and j == 1:
                tau = 1 + lam * rho
            elif i == 1 and j == 0:
                tau = 1 + mu * rho
            elif i == 1 and j == 1:
                tau = max(1 - rho, 1e-10)
            else:
                tau = 1.0
            prob[i][j] = max(tau * p, 0)

    total = sum(sum(row) for row in prob)
    if total > 0:
        for i in range(n):
            for j in range(n):
                prob[i][j] /= total

    home_win = sum(prob[i][j] for i in range(n) for j in range(n) if i > j)
    draw = sum(prob[i][i] for i in range(n))
    away_win = sum(prob[i][j] for i in range(n) for j in range(n) if i < j)

    best_score = (0, 0)
    best_prob = 0
    for i in range(n):
        for j in range(n):
            if prob[i][j] > best_prob:
                best_prob = prob[i][j]
                best_score = (i, j)

    over_25 = sum(prob[i][j] for i in range(n) for j in range(n) if i + j > 2)
    under_25 = 1 - over_25

    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
        "most_likely_score": f"{best_score[0]}-{best_score[1]}",
        "over_25": round(over_25, 4),
        "under_25": round(under_25, 4),
        "prob_matrix": prob,
    }


def _dc_build_sampler(lam, mu, rho, max_goals=8):
    """Pre-compute a flat probability array for fast repeated sampling."""
    from scipy.stats import poisson
    n = max_goals + 1
    probs = []
    for i in range(n):
        for j in range(n):
            p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
            if i == 0 and j == 0:
                tau = max(1 - lam * mu * rho, 1e-10)
            elif i == 0 and j == 1:
                tau = 1 + lam * rho
            elif i == 1 and j == 0:
                tau = 1 + mu * rho
            elif i == 1 and j == 1:
                tau = max(1 - rho, 1e-10)
            else:
                tau = 1.0
            probs.append(max(tau * p, 0))
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]
    return probs, n


def _dc_sample_from_sampler(probs, n, n_samples=1):
    """Fast sampling from pre-computed distribution."""
    import random
    home_goals = []
    away_goals = []
    for _ in range(n_samples):
        r = random.random()
        cumulative = 0
        for idx, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                home_goals.append(idx // n)
                away_goals.append(idx % n)
                break
    return home_goals, away_goals


def _dc_sample_scores(lam, mu, rho, n_samples=5000, max_goals=8):
    """Monte Carlo sampling from DC distribution."""
    import random
    result = _dc_prob_matrix(lam, mu, rho, max_goals=max_goals)
    prob = result["prob_matrix"]
    n = len(prob)
    flat = []
    for i in range(n):
        for j in range(n):
            flat.append(max(prob[i][j], 0))
    total = sum(flat)
    if total > 0:
        flat = [p / total for p in flat]
    home_goals = []
    away_goals = []
    for _ in range(n_samples):
        r = random.random()
        cumulative = 0
        for idx, p in enumerate(flat):
            cumulative += p
            if r <= cumulative:
                home_goals.append(idx // n)
                away_goals.append(idx % n)
                break
    return home_goals, away_goals


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
    cache_key = f"{home_team}_{away_team}_{context.get('stage','group')}_{context.get('is_host',False)}"
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
    
    # Apply goal multiplier to xG (lower goals in knockout stages)
    if adj['goal_mult'] != 1.0:
        xg['home'] = round(xg['home'] * adj['goal_mult'], 2)
        xg['away'] = round(xg['away'] * adj['goal_mult'], 2)
    
    # Apply host advantage bonus (significant boost for host nation)
    is_host = context.get('is_host', False)
    if is_host:
        # Host advantage: boost home_win, reduce away_win, keep draw stable.
        # Shift is applied proportionally so probabilities always sum to 1.
        host_bonus = 0.08
        hw = wdl['home_win'] + host_bonus
        aw = max(wdl['away_win'] - host_bonus * 0.5, 0.01)
        dw = wdl['draw']
        total = hw + aw + dw
        wdl['home_win'] = round(hw / total, 4)
        wdl['away_win'] = round(aw / total, 4)
        wdl['draw'] = round(1.0 - wdl['home_win'] - wdl['away_win'], 4)
        # Also boost xG slightly for host
        xg['home'] = round(xg['home'] * 1.08, 2)
    
    # Apply draw shift for knockout stages
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
        'over_under': _compute_over_under(xg),
        
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


def _compute_over_under(xg):
    """Compute over/under 2.5 probabilities from expected goals."""
    from scipy.stats import poisson
    lam_h = xg['home']
    lam_a = xg['away']
    
    # P(total goals > 2.5) = 1 - P(0,1,2 total goals)
    over_25 = 0.0
    for i in range(10):
        for j in range(10):
            if i + j > 2:
                over_25 += poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    
    under_25 = 1.0 - over_25
    return {'over_25': round(over_25, 4), 'under_25': round(under_25, 4)}


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

