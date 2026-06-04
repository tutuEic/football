# -*- coding: utf-8 -*-
"""
International match features for Poisson regression.

Features inspired by Groll et al. (2015):
"Prediction of major international soccer tournaments based on
 team-specific regularized Poisson regression"

23 features across 4 categories:
- Player Elo (8): team strength from player data
- Team Form (8): recent international results
- Head-to-Head (4): historical matchup
- Tournament (3): context features
"""
import sys
import os
import math
from datetime import date, datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_player_elo import calculate_elo_for_team, get_position_category
from engine.wc_elo_adapter import analyze_squad_elo
from engine.wc_dc_international import normalize_team

# Cache for expensive computations
_cache = {}


def _get_cached(key):
    if key in _cache:
        return _cache[key]
    return None


def _set_cached(key, value):
    _cache[key] = value


# ============================================================
# 1. Player Elo Features (8)
# ============================================================

def get_team_elo_features(team):
    """Get Elo-based features for a team."""
    cache_key = ('elo', team)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    try:
        analysis = analyze_squad_elo(team)
        result = {
            'team_avg_elo':     analysis['starting_xi'],
            'top11_elo':        analysis['starting_xi'],
            'elo_depth':        analysis['squad_depth'],
            'attack_quality':   analysis['attack_quality'],
            'defense_quality':  analysis['defense_quality'],
            'gk_elo':           analysis.get('gk_elo', 50),
            'star_player_elo':  analysis['elo_bonus'],
            'intl_experience':  len([p for p in analysis.get('elo_players', []) if p.get('intl_apps', 0) > 0]),
        }
    except Exception:
        result = {
            'team_avg_elo': 50, 'top11_elo': 50, 'elo_depth': 50,
            'attack_quality': 50, 'defense_quality': 50,
            'gk_elo': 50, 'star_player_elo': 0, 'intl_experience': 0,
        }
    
    _set_cached(cache_key, result)
    return result


# ============================================================
# 2. Team Form Features (8)
# ============================================================

def get_team_form(team, n_matches=10):
    """Get recent international form."""
    cache_key = ('form', team, n_matches)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    rows = query(
        "SELECT home_club_name, away_club_name, home_club_goals, away_club_goals, "
        "competition_id, date FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND (home_club_name = %s OR away_club_name = %s) "
        "AND home_club_goals IS NOT NULL "
        "AND date >= '2022-01-01' "
        "ORDER BY date DESC LIMIT %s",
        [team, team, n_matches], db='football_pred'
    )
    
    if not rows:
        result = {
            'form_points': 0.5, 'form_goals': 1.0, 'form_conceded': 1.0,
            'form_goal_diff': 0, 'form_wins': 0.3, 'form_clean_sheets': 0.2,
            'form_discipline': 0, 'form_matches': 0,
        }
        _set_cached(cache_key, result)
        return result
    
    points = 0
    goals_for = 0
    goals_against = 0
    wins = 0
    clean_sheets = 0
    
    for r in rows:
        is_home = normalize_team(r['home_club_name']) == team
        gf = r['home_club_goals'] if is_home else r['away_club_goals']
        ga = r['away_club_goals'] if is_home else r['home_club_goals']
        
        goals_for += gf
        goals_against += ga
        
        if gf > ga:
            points += 3
            wins += 1
        elif gf == ga:
            points += 1
        
        if ga == 0:
            clean_sheets += 1
    
    n = len(rows)
    result = {
        'form_points':      round(points / (n * 3), 3),
        'form_goals':       round(goals_for / n, 3),
        'form_conceded':    round(goals_against / n, 3),
        'form_goal_diff':   round((goals_for - goals_against) / n, 3),
        'form_wins':        round(wins / n, 3),
        'form_clean_sheets': round(clean_sheets / n, 3),
        'form_discipline':  0,  # TODO: add card data
        'form_matches':     n,
    }
    
    _set_cached(cache_key, result)
    return result


# ============================================================
# 3. Head-to-Head Features (4)
# ============================================================

def get_head_to_head(team_a, team_b):
    """Get head-to-head record."""
    cache_key = ('h2h', team_a, team_b)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    rows = query(
        "SELECT home_club_name, away_club_name, home_club_goals, away_club_goals "
        "FROM tm_games "
        "WHERE ((home_club_name = %s AND away_club_name = %s) "
        "OR (home_club_name = %s AND away_club_name = %s)) "
        "AND home_club_goals IS NOT NULL AND date >= '2014-01-01'",
        [team_a, team_b, team_b, team_a], db='football_pred'
    )
    
    # Minimum matches for reliable H2H data
    MIN_H2H_MATCHES = 5
    
    if not rows or len(rows) < MIN_H2H_MATCHES:
        # Not enough data: use neutral prior (equal win/draw/loss)
        result = {'h2h_wins': 0.33, 'h2h_draws': 0.33, 'h2h_losses': 0.33, 'h2h_matches': len(rows) if rows else 0}
        _set_cached(cache_key, result)
        return result
    
    wins = draws = losses = 0
    for r in rows:
        is_a_home = r['home_club_name'] == team_a
        gf = r['home_club_goals'] if is_a_home else r['away_club_goals']
        ga = r['away_club_goals'] if is_a_home else r['home_club_goals']
        
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1
    
    n = len(rows)
    result = {
        'h2h_wins':    round(wins / n, 3),
        'h2h_draws':   round(draws / n, 3),
        'h2h_losses':  round(losses / n, 3),
        'h2h_matches': n,
    }
    
    _set_cached(cache_key, result)
    return result


# ============================================================
# 4. Tournament Context Features (3)
# ============================================================

def get_fifa_ranking(team):
    """Get FIFA ranking points from wc_groups table."""
    cache_key = ('ranking', team)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    rows = query(
        "SELECT elo_rating FROM wc_groups WHERE team = %s",
        [team], db='football_pred'
    )
    
    result = float(rows[0]['elo_rating']) if rows else 1500.0
    _set_cached(cache_key, result)
    return result


def get_tournament_experience(team):
    """Count major tournament appearances since 2014."""
    cache_key = ('tournament_exp', team)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    rows = query(
        "SELECT COUNT(DISTINCT CONCAT(competition_id, YEAR(date))) as cnt "
        "FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN') "
        "AND (home_club_name = %s OR away_club_name = %s) "
        "AND date >= '2014-01-01'",
        [team, team], db='football_pred'
    )
    
    result = int(rows[0]['cnt']) if rows else 0
    _set_cached(cache_key, result)
    return result


# ============================================================
# Feature Computation for a Match
# ============================================================

FEATURE_NAMES = [
    # Elo features (8) - differences (home - away)
    'team_avg_elo_diff', 'top11_elo_diff', 'elo_depth_diff',
    'attack_quality_diff', 'defense_quality_diff',
    'gk_elo_diff', 'star_elo_diff', 'intl_exp_diff',
    
    # Form features (8) - differences
    'form_points_diff', 'form_goals_diff', 'form_conceded_diff',
    'form_goal_diff_diff', 'form_wins_diff',
    'form_clean_sheets_diff', 'form_discipline_diff', 'form_matches_diff',
    
    # Head-to-head (4)
    'h2h_wins', 'h2h_draws', 'h2h_losses', 'h2h_matches',
    
    # Context (3)
    'fifa_ranking_diff', 'tournament_exp_diff', 'home_advantage',
]


def compute_match_features(home_team, away_team):
    """Compute all features for a match (home - away differences)."""
    # Normalize names
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)
    
    # Elo features
    elo_h = get_team_elo_features(home_team)
    elo_a = get_team_elo_features(away_team)
    
    # Form features
    form_h = get_team_form(home_team)
    form_a = get_team_form(away_team)
    
    # H2H
    h2h = get_head_to_head(home_team, away_team)
    
    # Context
    rank_h = get_fifa_ranking(home_team)
    rank_a = get_fifa_ranking(away_team)
    exp_h = get_tournament_experience(home_team)
    exp_a = get_tournament_experience(away_team)
    
    features = {
        # Elo diffs
        'team_avg_elo_diff':    elo_h['team_avg_elo'] - elo_a['team_avg_elo'],
        'top11_elo_diff':       elo_h['top11_elo'] - elo_a['top11_elo'],
        'elo_depth_diff':       elo_h['elo_depth'] - elo_a['elo_depth'],
        'attack_quality_diff':  elo_h['attack_quality'] - elo_a['attack_quality'],
        'defense_quality_diff': elo_h['defense_quality'] - elo_a['defense_quality'],
        'gk_elo_diff':          elo_h['gk_elo'] - elo_a['gk_elo'],
        'star_elo_diff':        elo_h['star_player_elo'] - elo_a['star_player_elo'],
        'intl_exp_diff':        elo_h['intl_experience'] - elo_a['intl_experience'],
        
        # Form diffs
        'form_points_diff':     form_h['form_points'] - form_a['form_points'],
        'form_goals_diff':      form_h['form_goals'] - form_a['form_goals'],
        'form_conceded_diff':   form_h['form_conceded'] - form_a['form_conceded'],
        'form_goal_diff_diff':  form_h['form_goal_diff'] - form_a['form_goal_diff'],
        'form_wins_diff':       form_h['form_wins'] - form_a['form_wins'],
        'form_clean_sheets_diff': form_h['form_clean_sheets'] - form_a['form_clean_sheets'],
        'form_discipline_diff': form_h['form_discipline'] - form_a['form_discipline'],
        'form_matches_diff':    form_h['form_matches'] - form_a['form_matches'],
        
        # H2H
        'h2h_wins':     h2h['h2h_wins'],
        'h2h_draws':    h2h['h2h_draws'],
        'h2h_losses':   h2h['h2h_losses'],
        'h2h_matches':  h2h['h2h_matches'],
        
        # Context
        'fifa_ranking_diff':    (rank_h - rank_a) / 100.0,  # Scale
        'tournament_exp_diff':  exp_h - exp_a,
        'home_advantage':       1.0,  # Home team indicator
    }
    
    return features


def clear_feature_cache():
    """Clear feature cache."""
    global _cache
    _cache = {}

