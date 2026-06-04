# -*- coding: utf-8 -*-
"""
World Cup Prediction Engine 鈥?6-Layer Model
============================================
Predicts WC matches using:
  Layer 1: Player Elo (from wc_data.py)
  Layer 2: Base Elo (FIFA ranking + confederation calibration)
  Layer 3: Strength Decomposition (Elo -> alpha/beta for Dixon-Coles)
  Layer 4: Form & Momentum (recent international results)
  Layer 5: Tournament Factors (WC history, curses, continental style)
  Layer 6: Match Context (home advantage, stage, fatigue)

Model: Adapted Dixon-Coles with rho = -0.15 (more conservative than leagues)
No trained DC model 鈥?all strength derived from Elo + player data.
"""
import math
import sys
import os
from datetime import date, datetime, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_data import (
    analyze_squad, _country_name, COUNTRY_MAP,
    LEAGUE_QUALITY, DOMESTIC_LEAGUE,
)

# ============================================================
# Constants
# ============================================================

# Dixon-Coles rho for internationals (more conservative)
DC_RHO = 0.10          # Calibrated from 144 WC group matches (2014-2022)

# Confederation strength factors
CONFED_FACTOR = {
    "UEFA":     1.00,
    "CONMEBOL": 0.98,
    "CAF":      0.92,
    "CONCACAF": 0.90,
    "AFC":      0.88,
    "OFC":      0.78,
}



# Stage-specific rho (calibrated from historical WC data)
# Group stage: positive rho (more 0-0, 1-1 than Poisson expects)
# Knockout: negative rho (fewer draws, more decisive results)
STAGE_RHO = {
    "group":  0.10,    # 144 matches, Brier improved from 0.593 to 0.583
    "r16":   -0.15,    # 24 matches, knockout dynamics
    "qf":    -0.15,    # 12 matches
    "sf":    -0.12,    # 6 matches
    "final": -0.10,    # 3 matches
    "third":  0.00,    # 3 matches, less pressure
}

# Historical WC averages (2014-2022, group stage)
WC_GROUP_AVG_HOME = 1.326   # Actual avg home goals
WC_GROUP_AVG_AWAY = 1.299   # Actual avg away goals
WC_GROUP_DRAW_RATE = 0.194  # Actual draw rate (19.4%)
WC_KO_HOME_WIN_RATE = 0.578 # Knockout home win rate (57.8%)

# Host nation historical performance (2014-2022)
HOST_GROUP_RECORD = {
    # year: (W, D, L, GF, GA)
    2014: (2, 1, 0, 7, 2),   # Brazil: strong host
    2018: (2, 0, 1, 8, 4),   # Russia: decent host
    2022: (0, 0, 3, 1, 7),   # Qatar: worst host ever
}
# Home advantage (Elo points)
HOME_ADVANTAGE_ELO = 50      # Reduced: WC data shows limited host advantage (calibrated)
NEUTRAL_CROWD_ELO  = 10      # Reduced: WC group stage away wins more (calibrated)
KNOCKOUT_HOME_MULT = 0.5     # Reduced home advantage in knockout

# Stage goal multiplier and draw shift
STAGE_FACTORS = {
    "group_md1":  {"goal_mult": 1.02, "draw_shift": -0.02},
    "group_md2":  {"goal_mult": 1.00, "draw_shift": -0.01},
    "group_md3":  {"goal_mult": 0.95, "draw_shift":  0.02},
    "r32":        {"goal_mult": 0.92, "draw_shift":  0.03},
    "r16":        {"goal_mult": 0.90, "draw_shift":  0.04},
    "qf":         {"goal_mult": 0.88, "draw_shift":  0.03},
    "sf":         {"goal_mult": 0.85, "draw_shift":  0.04},
    "final":      {"goal_mult": 0.82, "draw_shift":  0.05},
}

# WC historical best results (Elo bonus)
WC_HISTORY = {
    # Multiple-time winners
    "Brazil":          40, "Germany":         40, "Italy":           40,
    "Argentina":       25, "France":          25, "England":         25,
    "Spain":           25, "Uruguay":         25,
    # Historical finalists / semi-finalists
    "Netherlands":     15, "Croatia":          8, "Czechia":          8,
    "Hungary":         8,  "Sweden":           8, "Poland":           3,
    "Belgium":         3,  "Portugal":         3, "Turkey":           3,
    "T眉rkiye":         3,  "Korea Republic":   3, "USA":              3,
    "Chile":           3,  "Bulgaria":         3, "Austria":          3,
    "Russia":          3,  "Senegal":          3, "Morocco":          3,
    "Mexico":          1,  "Switzerland":      1, "Japan":            1,
    "Colombia":        1,  "Denmark":          1, "Paraguay":         1,
    "Nigeria":         1,  "Cameroon":         1, "Ghana":            1,
    "Ireland":         1,  "Wales":            1, "Scotland":         1,
    "Norway":          1,  "Romania":          1,
    # First-time or rare participants get default 0
}

# Defending champion (2022 winner)
DEFENDING_CHAMPION = "Argentina"

# Continental style adjustments (alpha bonus when styles clash)
# Format: (conf_a, conf_b) -> alpha bonus for conf_a
STYLE_CLASH = {
    ("UEFA", "CAF"):      0.02,
    ("CONMEBOL", "AFC"):  0.03,
    ("CONMEBOL", "CAF"):  0.02,
    ("UEFA", "AFC"):      0.01,
    ("UEFA", "CONCACAF"): 0.01,
}


# ============================================================
# Layer 2: Base Elo + Confederation
# ============================================================

# Module-level cache for base Elo data
_ELO_CACHE = {}

def get_team_base_elo(fifa_country_name):
    """Get FIFA Elo rating from wc_groups table."""
    if fifa_country_name in _ELO_CACHE:
        return _ELO_CACHE[fifa_country_name]
    rows = query(
        "SELECT elo_rating, confederation, appearances FROM wc_groups WHERE team = %s",
        [fifa_country_name], db="football_pred"
    )
    if rows:
        result = {
            "elo": float(rows[0]["elo_rating"] or 1500),
            "confederation": rows[0]["confederation"] or "UEFA",
            "appearances": int(rows[0]["appearances"] or 0),
        }
    else:
        result = {"elo": 1500, "confederation": "UEFA", "appearances": 0}
    _ELO_CACHE[fifa_country_name] = result
    return result


def confederation_adjustment(home_conf, away_conf):
    """Cross-confederation Elo adjustment."""
    own_factor = CONFED_FACTOR.get(home_conf, 0.90)
    opp_factor = CONFED_FACTOR.get(away_conf, 0.90)
    return round((opp_factor - own_factor) * 20, 2)


# ============================================================
# Layer 3: Strength Decomposition (Elo -> alpha, beta)
# ============================================================

def decompose_elo(combined_elo, attack_quality, defense_quality):
    """
    Convert combined Elo to Dixon-Coles alpha (attack) and beta (defense).

    Calibrated against real WC results (2014-2022):
      - Brazil vs weak team: xG ~3.0-3.5
      - Top team vs mid-tier: xG ~1.8-2.2
      - Even match: xG ~1.2-1.4 each

    alpha = attack strength (higher = more goals scored)
    beta  = defense weakness (higher = more goals conceded)
    """
    base_alpha = (combined_elo - 1500) / 500 * 0.7
    base_beta  = -(combined_elo - 1500) / 500 * 0.7

    # Player quality adjustments
    # Low defense_quality = weak defense = HIGHER beta (more goals conceded)
    att_q = (attack_quality - 70) / 30
    def_q = (defense_quality - 70) / 30

    alpha = base_alpha + att_q * 0.20
    beta  = base_beta  - def_q * 0.15  # negative: low def_quality -> higher beta

    return round(alpha, 4), round(beta, 4)


# ============================================================
# Layer 4: Form & Momentum
# ============================================================

# Module-level cache for form data (cleared manually if needed)
_FORM_CACHE = {}

def clear_form_cache():
    """Clear the form cache (e.g., after updating match results)."""
    global _FORM_CACHE
    _FORM_CACHE = {}

def get_international_form(fifa_country_name):
    """
    Calculate recent international form from tm_games.
    Looks at competitive internationals from 2023+.
    Returns form score in range roughly -1.0 to +1.0.
    """
    # Check cache first
    if fifa_country_name in _FORM_CACHE:
        return _FORM_CACHE[fifa_country_name]

    country = _country_name(fifa_country_name)

    # Try to find national team matches by checking tm_games
    rows = query("""
        SELECT g.game_id, g.date, g.competition_id, g.home_club_name, g.away_club_name,
               g.home_club_goals, g.away_club_goals
        FROM tm_games g
        WHERE g.competition_id IN ('FIWC', 'EURO', 'COPA', 'AFAC', 'AFCN', 'WCQL', 'EUCON', 'AFQL', 'ACQL', 'UNL', 'CNL', 'GC', 'FR')
          AND g.date >= '2022-01-01'
          AND (g.home_club_name LIKE %s OR g.away_club_name LIKE %s)
        ORDER BY g.date DESC
        LIMIT 30
    """, [f"%{fifa_country_name}%", f"%{fifa_country_name}%"], db="football_pred")

    if not rows:
        # Try with mapped country name
        rows = query("""
            SELECT g.game_id, g.date, g.competition_id, g.home_club_name, g.away_club_name,
                   g.home_club_goals, g.away_club_goals
            FROM tm_games g
            WHERE g.competition_id IN ('FIWC', 'EURO', 'COPA', 'AFAC', 'AFCN', 'WCQL', 'EUCON', 'AFQL', 'ACQL', 'UNL', 'CNL', 'GC', 'FR')
              AND g.date >= '2022-01-01'
              AND (g.home_club_name LIKE %s OR g.away_club_name LIKE %s)
            ORDER BY g.date DESC
            LIMIT 30
        """, [f"%{country}%", f"%{country}%"], db="football_pred")

    if not rows:
        return 0.0

    # Competition weights
    comp_weight = {
        "FIWC": 1.0, "WCQL": 1.0,
        "EURO": 0.8, "COPA": 0.8, "AFAC": 0.8, "AFCN": 0.8,
        "EUCON": 0.6,
    }

    form = 0.0
    total_weight = 0.0
    today = date.today()

    for i, r in enumerate(rows):
        comp = r.get("competition_id", "")
        w = comp_weight.get(comp, 0.4)

        # Recency decay
        match_date = r.get("date")
        if match_date:
            days_ago = (today - match_date).days
            decay = math.exp(-0.005 * days_ago)  # ~50% after 140 days
        else:
            decay = 1.0

        effective_w = w * decay

        # Determine if this team won/drew/lost
        is_home = fifa_country_name in (r.get("home_club_name") or "") or country in (r.get("home_club_name") or "")
        if is_home:
            gf = int(r.get("home_club_goals") or 0)
            ga = int(r.get("away_club_goals") or 0)
        else:
            gf = int(r.get("away_club_goals") or 0)
            ga = int(r.get("home_club_goals") or 0)

        # Result score
        diff = gf - ga
        if diff >= 2:
            result = 1.2
        elif diff == 1:
            result = 1.0
        elif diff == 0:
            result = 0.3
        elif diff == -1:
            result = -0.5
        else:
            result = -0.8

        form += result * effective_w
        total_weight += effective_w

    if total_weight > 0:
        form /= total_weight
    result = round(form, 3)
    _FORM_CACHE[fifa_country_name] = result
    return result


# ============================================================
# Layer 5: Tournament Factors
# ============================================================

def get_wc_history_bonus(fifa_country_name):
    """WC historical performance bonus."""
    # Try both FIFA name and mapped name
    bonus = WC_HISTORY.get(fifa_country_name, 0)
    if bonus == 0:
        mapped = _country_name(fifa_country_name)
        bonus = WC_HISTORY.get(mapped, 0)
    return bonus


def get_historical_curse(fifa_country_name):
    """Apply statistical 'curses' (defending champion, first-timer)."""
    curse = 0

    # Defending champion curse
    mapped = _country_name(fifa_country_name)
    if fifa_country_name == DEFENDING_CHAMPION or mapped == DEFENDING_CHAMPION:
        curse -= 15

    # First-time participant penalty
    base = get_team_base_elo(fifa_country_name)
    if base["appearances"] <= 1:
        curse -= 10

    return curse


def get_continental_style(home_conf, away_conf):
    """Continental style clash adjustment (alpha bonus for home team)."""
    adj = STYLE_CLASH.get((home_conf, away_conf), 0)
    return adj


# ============================================================
# Layer 6: Match Context
# ============================================================

def get_home_advantage(home_team, away_team, context):
    """
    Calculate home advantage in Elo points.
    context: dict with 'stage', 'is_host', 'venue_country'
    """
    stage = context.get("stage", "group")
    is_host = context.get("is_host", False)
    in_host_country = context.get("in_host_country", True)

    if is_host:
        gamma = HOME_ADVANTAGE_ELO
    elif in_host_country:
        gamma = NEUTRAL_CROWD_ELO
    else:
        gamma = 0

    # Reduce in knockout stages
    if stage != "group":
        gamma *= KNOCKOUT_HOME_MULT if is_host else 0

    return gamma


def get_stage_factors(context):
    """Get goal multiplier and draw shift for the match stage."""
    stage = context.get("stage", "group")
    matchday = context.get("matchday", 1)

    if stage == "group":
        key = f"group_md{matchday}"
    else:
        key = stage

    factors = STAGE_FACTORS.get(key, {"goal_mult": 1.0, "draw_shift": 0.0})
    return factors["goal_mult"], factors["draw_shift"]


# ============================================================
# Core Prediction: Dixon-Coles for Internationals
# ============================================================

def _dc_prob_matrix(lam, mu, rho=None, stage="group", max_goals=8):
    """
    Compute Dixon-Coles probability matrix with tau correction.
    Uses stage-specific rho when available.
    """
    if rho is None:
        rho = STAGE_RHO.get(stage, DC_RHO)
    from scipy.stats import poisson

    n = max_goals + 1
    prob = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
            # Tau correction for low scores
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

    # Normalize
    total = sum(sum(row) for row in prob)
    if total > 0:
        for i in range(n):
            for j in range(n):
                prob[i][j] /= total

    # Compute WDL
    home_win = sum(prob[i][j] for i in range(n) for j in range(n) if i > j)
    draw     = sum(prob[i][i] for i in range(n))
    away_win = sum(prob[i][j] for i in range(n) for j in range(n) if i < j)

    # Most likely score
    best_score = (0, 0)
    best_prob = 0
    for i in range(n):
        for j in range(n):
            if prob[i][j] > best_prob:
                best_prob = prob[i][j]
                best_score = (i, j)

    # Over/under 2.5
    over_25 = sum(prob[i][j] for i in range(n) for j in range(n) if i + j > 2)
    under_25 = 1 - over_25
    over_35 = sum(prob[i][j] for i in range(n) for j in range(n) if i + j > 3)
    over_45 = sum(prob[i][j] for i in range(n) for j in range(n) if i + j > 4)

    # Score distribution (top scores)
    scores = {}
    for i in range(min(5, n)):
        for j in range(min(5, n)):
            key = f"{i}-{j}"
            scores[key] = round(prob[i][j], 4)

    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
        "most_likely_score": f"{best_score[0]}-{best_score[1]}",
        "most_likely_prob": round(best_prob, 4),
        "over_25": round(over_25, 4),
        "over_35": round(over_35, 4),
        "over_45": round(over_45, 4),
        "under_25": round(under_25, 4),
        "score_distribution": scores,
        "prob_matrix": prob,
    }


def _dc_build_sampler(lam, mu, rho, max_goals=8):
    """
    Pre-compute a flat probability array for fast repeated sampling.
    Returns (flat_probs, n) where n is the grid size.
    """
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

    # Build probability matrix once
    result = _dc_prob_matrix(lam, mu, rho, max_goals)
    prob = result["prob_matrix"]
    n = len(prob)

    # Flatten for sampling
    flat = []
    for i in range(n):
        for j in range(n):
            flat.append(max(prob[i][j], 0))
    total = sum(flat)
    if total > 0:
        flat = [p / total for p in flat]

    # Sample
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


# ============================================================
# Main Entry: Predict a WC Match
# ============================================================

def predict_wc_match(home_team, away_team, context=None,
                     analysis_home=None, analysis_away=None):
    """
    Predict a World Cup match using the 6-layer model.

    Args:
        home_team: FIFA country name (e.g., "France")
        away_team: FIFA country name (e.g., "Brazil")
        context: dict with keys:
            - stage: "group", "r32", "r16", "qf", "sf", "final"
            - matchday: 1, 2, 3 (group stage only)
            - is_host: bool (home team is host nation)
            - in_host_country: bool (match played in host country)
            - group: "A"-"L" (group stage only)
        analysis_home: pre-computed analyze_squad() result for home team
        analysis_away: pre-computed analyze_squad() result for away team

    Returns:
        Full prediction dict with probabilities, expected goals,
        score distribution, and all factor breakdowns.
    """
    if context is None:
        context = {"stage": "group", "matchday": 1, "is_host": False, "in_host_country": True}

    # === Layer 1: Player Elo ===
    analysis_h = analysis_home if analysis_home else analyze_squad(home_team)
    analysis_a = analysis_away if analysis_away else analyze_squad(away_team)

    player_elo_h = analysis_h["elo_bonus"]
    player_elo_a = analysis_a["elo_bonus"]

    # === Layer 2: Base Elo + Confederation ===
    base_h = get_team_base_elo(home_team)
    base_a = get_team_base_elo(away_team)

    conf_adj = confederation_adjustment(base_h["confederation"], base_a["confederation"])

    combined_elo_h = base_h["elo"] + player_elo_h + conf_adj
    combined_elo_a = base_a["elo"] + player_elo_a - conf_adj

    # === Layer 3: Strength Decomposition ===
    alpha_h, beta_h = decompose_elo(
        combined_elo_h, analysis_h["attack_quality"], analysis_h["defense_quality"]
    )
    alpha_a, beta_a = decompose_elo(
        combined_elo_a, analysis_a["attack_quality"], analysis_a["defense_quality"]
    )

    # === Layer 4: Form ===
    form_h = get_international_form(home_team)
    form_a = get_international_form(away_team)

    # === Layer 5: Tournament Factors ===
    wc_hist_h = get_wc_history_bonus(home_team)
    wc_hist_a = get_wc_history_bonus(away_team)

    curse_h = get_historical_curse(home_team)
    curse_a = get_historical_curse(away_team)

    # Convert WC history/curse to alpha adjustment
    tournament_adj_h = (wc_hist_h + curse_h) / 1000
    tournament_adj_a = (wc_hist_a + curse_a) / 1000

    # Continental style
    style_h = get_continental_style(base_h["confederation"], base_a["confederation"])
    style_a = get_continental_style(base_a["confederation"], base_h["confederation"])

    # === Layer 6: Match Context ===
    gamma = get_home_advantage(home_team, away_team, context)
    goal_mult, draw_shift = get_stage_factors(context)

    # === Expected Goals (Dixon-Coles) ===
    lam = math.exp(alpha_h + beta_a + gamma / 400 + tournament_adj_h + style_h)
    mu  = math.exp(alpha_a + beta_h + tournament_adj_a + style_a)

    # Apply form adjustment
    lam *= (1 + form_h * 0.15)
    mu  *= (1 + form_a * 0.15)

    # Apply stage goal multiplier
    lam *= goal_mult
    mu  *= goal_mult

    # Clamp to reasonable range
    lam = max(0.15, min(lam, 4.0))
    mu  = max(0.10, min(mu, 3.5))

    # === Compute Probabilities ===
    result = _dc_prob_matrix(lam, mu, stage=context.get("stage", "group"))

    # Apply draw shift
    if draw_shift != 0:
        total_non_draw = result["home_win"] + result["away_win"]
        if total_non_draw > 0:
            # Shift probability from win/loss to draw
            shift = draw_shift
            new_draw = min(max(result["draw"] + shift, 0.05), 0.50)
            actual_shift = new_draw - result["draw"]
            scale = (total_non_draw - actual_shift) / total_non_draw if total_non_draw > 0 else 1
            result["home_win"] = round(max(result["home_win"] * scale, 0.01), 4)
            result["away_win"] = round(max(result["away_win"] * scale, 0.01), 4)
            result["draw"] = round(new_draw, 4)

    # === Build full response ===
    elo_diff = round(combined_elo_h - combined_elo_a, 1)

    # Confidence: based on Elo difference
    confidence = round(min(abs(elo_diff) / 300, 1.0), 2)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "stage": context.get("stage", "group"),
        "matchday": context.get("matchday", 1),
        "model_version": "wc_v2_calibrated",

        "expected_goals": result["expected_goals"],
        "wdl": {
            "home_win": result["home_win"],
            "draw": result["draw"],
            "away_win": result["away_win"],
        },
        "most_likely_score": result["most_likely_score"],
        "most_likely_prob": result["most_likely_prob"],
        "over_under": {
            "over_25": result["over_25"],
            "under_25": result["under_25"],
            "over_35": result.get("over_35", 0),
            "over_45": result.get("over_45", 0),
        },
        "score_distribution": result["score_distribution"],
        "confidence": confidence,

        "player_analysis": {
            "home": {
                "starting_xi": analysis_h["starting_xi"],
                "attack_quality": analysis_h["attack_quality"],
                "defense_quality": analysis_h["defense_quality"],
                "squad_depth": analysis_h["squad_depth"],
                "avg_age": analysis_h["avg_age"],
                "age_score": analysis_h["age_score"],
                "league_quality": analysis_h["league_quality"],
                "cohesion": analysis_h["cohesion"],
                "set_piece_strength": analysis_h["set_piece_strength"],
                "elo_bonus": analysis_h["elo_bonus"],
                "top_players": analysis_h["top_players"],
            },
            "away": {
                "starting_xi": analysis_a["starting_xi"],
                "attack_quality": analysis_a["attack_quality"],
                "defense_quality": analysis_a["defense_quality"],
                "squad_depth": analysis_a["squad_depth"],
                "avg_age": analysis_a["avg_age"],
                "age_score": analysis_a["age_score"],
                "league_quality": analysis_a["league_quality"],
                "cohesion": analysis_a["cohesion"],
                "set_piece_strength": analysis_a["set_piece_strength"],
                "elo_bonus": analysis_a["elo_bonus"],
                "top_players": analysis_a["top_players"],
            },
        },

        "factors": {
            "elo": {
                "home_fifa": base_h["elo"],
                "away_fifa": base_a["elo"],
                "player_elo": {"home": player_elo_h, "away": player_elo_a},
                "conf_adj": conf_adj,
                "combined": {"home": round(combined_elo_h, 1), "away": round(combined_elo_a, 1)},
                "diff": elo_diff,
            },
            "decomposition": {
                "alpha": {"home": alpha_h, "away": alpha_a},
                "beta": {"home": beta_h, "away": beta_a},
            },
            "form": {"home": form_h, "away": form_a},
            "tournament": {
                "wc_history": {"home": wc_hist_h, "away": wc_hist_a},
                "curse": {"home": curse_h, "away": curse_a},
                "style_adj": {"home": style_h, "away": style_a},
            },
            "context": {
                "home_advantage_gamma": gamma,
                "goal_mult": goal_mult,
                "draw_shift": draw_shift,
            },
        },
    }


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

    # Determine context from fixture
    # Group stage matches have group info in wc_groups
    group_rows = query(
        "SELECT group_name FROM wc_groups WHERE team = %s",
        [home], db="football_pred"
    )
    group = group_rows[0]["group_name"] if group_rows else None

    # Determine if host nation
    host_rows = query(
        "SELECT team FROM wc_groups WHERE is_host = 1",
        db="football_pred"
    )
    host_teams = [r["team"] for r in host_rows]

    context = {
        "stage": "group",
        "matchday": 1,  # Would need proper matchday tracking
        "is_host": home in host_teams,
        "in_host_country": True,
        "group": group,
    }

    return predict_wc_match(home, away, context)


def predict_all_group_matches():
    """Predict all WC2026 group stage matches from fixtures table."""
    rows = query(
        "SELECT * FROM fixtures WHERE league_code = 'WC2026' ORDER BY match_date, id",
        db="football_pred"
    )

    # Get host teams
    host_rows = query(
        "SELECT team FROM wc_groups WHERE is_host = 1", db="football_pred"
    )
    host_teams = {r["team"] for r in host_rows}

    # Get group assignments
    group_map = {}
    group_rows = query("SELECT team, group_name FROM wc_groups", db="football_pred")
    for r in group_rows:
        group_map[r["team"]] = r["group_name"]

    predictions = []
    for f in rows:
        home = f["home_team"]
        away = f["away_team"]
        group = group_map.get(home)

        # Determine matchday (simplified: by date order within group)
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
            print(f"[WC_PREDICTOR] Error predicting {home} vs {away}: {e}")

    return predictions


