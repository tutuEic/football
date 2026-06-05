# -*- coding: utf-8 -*-
"""
WC Elo Adapter - bridges wc_player_elo.py to wc_predictor.py interface.

Drop-in replacement for wc_data.analyze_squad() that uses the new
league + international Elo system instead of market-value-based strength.
"""
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_player_elo import (
    calculate_elo_for_team,
    get_position_category,
    load_player_appearances,
    load_player_metadata,
    calculate_player_elo,
    MIN_APPEARANCES,
)
from engine.wc_data import (
    _country_name,
    get_national_squad,
    calc_age_profile,
    calc_cohesion,
    calc_set_piece_strength,
    calc_league_quality,
)

# Cache for squad Elo analysis
_squad_elo_cache = {}


def analyze_squad_elo(fifa_country_name):
    """
    Analyze a national team using the Elo-based system.
    
    Returns dict compatible with wc_predictor.py's expected interface:
    - starting_xi, attack_quality, defense_quality, squad_depth (0-99)
    - elo_bonus (-60 to +120)
    - top_players, squad, etc.
    """
    if fifa_country_name in _squad_elo_cache:
        return _squad_elo_cache[fifa_country_name]
    
    # Get squad players with Elo ratings
    elo_players = calculate_elo_for_team(fifa_country_name, top_n=35)
    
    # Get raw squad data for age, cohesion, set piece calculations
    raw_squad = get_national_squad(fifa_country_name, top_n=35)
    
    # If no Elo data but have players, use market value fallback
    if not elo_players and raw_squad:
        return _market_value_fallback(fifa_country_name, raw_squad)
    
    if not elo_players:
        return _empty_analysis(fifa_country_name)
    
    # Build player lookup by id
    elo_by_id = {p['player_id']: p for p in elo_players}
    
    # Merge Elo data into squad
    squad = []
    for raw_p in raw_squad:
        pid = raw_p['player_id']
        elo_p = elo_by_id.get(pid)
        if elo_p:
            raw_p['elo'] = elo_p['elo']
            raw_p['league_elo'] = elo_p['league_elo']
            raw_p['intl_elo'] = elo_p['intl_elo']
            raw_p['strength'] = elo_p['elo']  # Use Elo as strength
        else:
            raw_p['elo'] = 50.0
            raw_p['league_elo'] = 50.0
            raw_p['intl_elo'] = None
            raw_p['strength'] = 50.0
        squad.append(raw_p)
    
    # Sort by Elo
    squad.sort(key=lambda p: p.get('elo', 0), reverse=True)
    
    # === Starting XI (1 GK + 4 DF + 3 MF + 3 FW) ===
    by_cat = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in squad:
        cat = p.get('pos_category', get_position_category(p.get('position'), p.get('sub_position')))
        by_cat.setdefault(cat, []).append(p)
    
    for cat in by_cat:
        by_cat[cat].sort(key=lambda p: p.get('elo', 0), reverse=True)
    
    xi_slots = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
    top_11 = []
    for cat, count in xi_slots.items():
        top_11.extend(by_cat.get(cat, [])[:count])
    
    # Fill if short
    if len(top_11) < 11:
        used_ids = {p['player_id'] for p in top_11}
        remaining = [p for p in squad if p['player_id'] not in used_ids]
        remaining.sort(key=lambda p: p.get('elo', 0), reverse=True)
        top_11.extend(remaining[:11 - len(top_11)])
    
    starting_xi = round(sum(p.get('elo', 50) for p in top_11) / max(len(top_11), 1), 1)
    
    # === Attack quality (top 5 attackers/midfielders) ===
    attackers = [p for p in squad if p.get('pos_category', 'MF') in ('FW', 'MF')]
    top_5_att = attackers[:5]
    attack_quality = round(sum(p.get('elo', 50) for p in top_5_att) / max(len(top_5_att), 1), 1)
    
    # === Defense quality (top 5 defenders + GK) ===
    defenders = [p for p in squad if p.get('pos_category', 'MF') in ('DF', 'GK')]
    top_5_def = defenders[:5]
    defense_quality = round(sum(p.get('elo', 50) for p in top_5_def) / max(len(top_5_def), 1), 1)
    
    # === Squad depth (top 23 average minus std penalty) ===
    top_23 = squad[:23]
    if len(top_23) >= 2:
        mean_23 = sum(p.get('elo', 50) for p in top_23) / len(top_23)
        variance = sum((p.get('elo', 50) - mean_23) ** 2 for p in top_23) / len(top_23)
        std_23 = variance ** 0.5
        squad_depth = round(mean_23 - std_23 * 0.3, 1)
    else:
        squad_depth = 50.0
    
    # === Age profile ===
    age_score, avg_age = calc_age_profile(squad)
    
    # === Cohesion ===
    cohesion = calc_cohesion(squad, fifa_country_name)
    
    # === Set piece ===
    setpiece = calc_set_piece_strength(squad)
    
    # === League quality ===
    league_q = calc_league_quality(squad)
    
    # === Elo bonus calculation ===
    # Starting XI bonus: scale around 65 as baseline
    xi_elo = round((starting_xi - 60) * 1.5, 1)  # Range: -30 to +60
    
    # Age bonus
    age_elo = round((age_score - 0.6) * 50, 1)  # Range: -30 to +20
    
    # League quality bonus
    league_elo = round((league_q - 70) * 0.5, 1)  # Range: -15 to +15
    
    # Cohesion bonus
    cohesion_elo = round((cohesion - 0.5) * 30, 1)  # Range: -15 to +15
    
    # Set piece bonus
    sp_elo = round((setpiece - 0.5) * 20, 1)  # Range: -10 to +10
    
    # Star player bonus (top player Elo > 75)
    star_elo = 0
    if squad and squad[0].get('elo', 0) > 75:
        star_elo = round((squad[0]['elo'] - 75) * 0.5, 1)
    
    # International experience bonus
    intl_players = [p for p in elo_players if p.get('intl_apps', 0) > 0]
    intl_ratio = len(intl_players) / max(len(elo_players), 1)
    intl_elo = round(intl_ratio * 10, 1)  # 0 to +10 for experienced squads
    
    total_elo = xi_elo + age_elo + league_elo + cohesion_elo + sp_elo + star_elo + intl_elo
    
    # Top players display
    top_5 = elo_players[:5]
    top_display = [f"{p['name']} ({p['elo']:.0f})" for p in top_5]
    
    result = {
        "country":          fifa_country_name,
        "tm_country":       _country_name(fifa_country_name),
        "squad_size":       len(squad),
        "starting_xi":      starting_xi,
        "attack_quality":   attack_quality,
        "defense_quality":  defense_quality,
        "squad_depth":      max(squad_depth, 0),
        "avg_age":          avg_age,
        "age_score":        age_score,
        "league_quality":   league_q,
        "cohesion":         cohesion,
        "set_piece_strength": setpiece,
        "elo_bonus":        round(total_elo, 1),
        "elo_breakdown": {
            "starting_xi": xi_elo,
            "age": age_elo,
            "league": league_elo,
            "cohesion": cohesion_elo,
            "set_piece": sp_elo,
            "star": star_elo,
            "intl_exp": intl_elo,
        },
        "top_players":      top_display,
        "squad":            squad,
        
        # Extra Elo-specific data
        "elo_system":       "v2_combined",
        "elo_players":      elo_players,
    }
    
    _squad_elo_cache[fifa_country_name] = result
    return result


def _market_value_fallback(country, raw_squad):
    """
    Fallback analysis when Elo data is unavailable but players exist.
    Uses market value to estimate team strength.
    """
    if not raw_squad:
        return _empty_analysis(country)
    
    # Sort by market value
    squad = sorted(raw_squad, key=lambda p: p.get('market_value', 0), reverse=True)
    
    # Top 11 market value
    top_11 = squad[:11]
    top_11_avg_mv = sum(p.get('market_value', 0) for p in top_11) / max(len(top_11), 1)
    
    # Convert market value to elo_bonus (log scale)
    # Reference: EUR 10M avg -> elo_bonus ~0, EUR 1M -> -15, EUR 50M -> +20
    import math
    if top_11_avg_mv > 0:
        mv_log = math.log10(top_11_avg_mv)
        # Scale: log10(1M)=6 -> -15, log10(10M)=7 -> 0, log10(50M)=7.7 -> +15
        elo_bonus = round((mv_log - 7) * 15, 1)
        elo_bonus = max(-30, min(elo_bonus, 30))  # Clamp to [-30, +30]
    else:
        elo_bonus = -20.0
    
    # Top players list
    top_players = []
    for p in squad[:10]:
        name = p.get('name', 'Unknown')
        mv = p.get('market_value', 0)
        # Estimate "rating" from market value for display
        if mv > 0:
            rating = min(99, max(50, int(50 + math.log10(mv) * 3)))
        else:
            rating = 50
        top_players.append(f"{name} ({rating})")
    
    return {
        "country": country, "tm_country": _country_name(country),
        "squad_size": len(squad), "starting_xi": 50.0, "attack_quality": 50.0,
        "defense_quality": 50.0, "squad_depth": 50.0, "avg_age": 25.0,
        "age_score": 0.5, "league_quality": 45.0, "cohesion": 0.4,
        "set_piece_strength": 0.5, "elo_bonus": elo_bonus,
        "elo_breakdown": {"starting_xi": elo_bonus, "age": 0, "league": 0,
                          "cohesion": 0, "set_piece": 0, "star": 0, "intl_exp": 0},
        "top_players": top_players, "squad": squad,
        "elo_system": "market_value_fallback", "elo_players": [],
    }


def _empty_analysis(country):
    """Return default analysis when no data found."""
    return {
        "country": country, "tm_country": _country_name(country),
        "squad_size": 0, "starting_xi": 50.0, "attack_quality": 50.0,
        "defense_quality": 50.0, "squad_depth": 50.0, "avg_age": 25.0,
        "age_score": 0.5, "league_quality": 45.0, "cohesion": 0.4,
        "set_piece_strength": 0.5, "elo_bonus": -20.0,
        "elo_breakdown": {"starting_xi": -20, "age": 0, "league": 0,
                          "cohesion": 0, "set_piece": 0, "star": 0, "intl_exp": 0},
        "top_players": [], "squad": [],
        "elo_system": "v2_combined", "elo_players": [],
    }


def clear_elo_cache():
    """Clear the squad Elo cache."""
    global _squad_elo_cache
    _squad_elo_cache = {}
