# -*- coding: utf-8 -*-
"""
Football prediction engine v3 鈥?Full mathematical framework
Fixed: Correct DC formula, proper injury/momentum scaling, tau-corrected sampling.
"""
import os, math, time, json
import numpy as np
from collections import Counter


from engine.predictor import load_model, predict_match as dc_predict
from data.tm_repo import search_club, get_club_squad
from engine.player_ratings import get_club_squad_rated, get_player_rating
from data.match_repo import query
from engine.simulator import MonteCarloSimulator
from features.feature_store import compute_match_features, FEATURE_NAMES


# ============================================================
# Ensemble prediction (DC + Poisson Regression + XGBoost)
# ============================================================
_ensemble_cache = {}
_ENSEMBLE_TTL = 600  # 10 min
_MAX_CACHE_SIZE = 500  # Max entries in cache

def _clean_ensemble_cache():
    """Remove expired entries and enforce max size."""
    global _ensemble_cache
    now = time.time()
    
    # Remove expired
    expired = [k for k, (ts, _) in _ensemble_cache.items() if now - ts > _ENSEMBLE_TTL]
    for k in expired:
        del _ensemble_cache[k]
    
    # If still too large, remove oldest
    if len(_ensemble_cache) > _MAX_CACHE_SIZE:
        sorted_keys = sorted(_ensemble_cache.keys(), key=lambda k: _ensemble_cache[k][0])
        for k in sorted_keys[:len(_ensemble_cache) - _MAX_CACHE_SIZE]:
            del _ensemble_cache[k]


def _load_ensemble_models(league="E0"):
    """Load all trained base models for ensemble prediction for a given league."""
    import json
    from pathlib import Path
    model_dir = Path(__file__).resolve().parent.parent / "models"

    models = {}

    # Poisson Regression
    try:
        from models.poisson_regression import PoissonRegression
        pr = PoissonRegression()
        pr_path = model_dir / f"poisson_{league}.json"
        if pr_path.exists():
            pr.load(pr_path)
            models["poisson"] = pr
    except Exception:
        pass

    # XGBoost
    try:
        from models.xgboost_model import XGBoostPredictor
        xgb = XGBoostPredictor()
        xgb_path = model_dir / f"xgboost_{league}.json"
        if xgb_path.exists():
            xgb.load(xgb_path)
            models["xgboost"] = xgb
    except Exception:
        pass

    # Time-Weighted Dixon-Coles (TW-DC)
    try:
        tw_files = sorted(model_dir.glob("dc_*_tw.json"), reverse=True)
        if tw_files:
            from engine.dixon_coles import DixonColes
            tw = DixonColes()
            with open(tw_files[0], "r", encoding="utf-8") as f:
                tw_data = json.load(f)
            tw.teams = tw_data["teams"]
            tw.params = tw_data["params"]
            tw.fitted = True
            models["tw_dc"] = tw
    except Exception:
        pass

    # Bayesian DC (P0-1: Bayesian hierarchical with time-varying params)
    try:
        bayes_files = sorted(model_dir.glob(f"bayes_dc_{league}_*.json"), reverse=True)
        bayes_path = bayes_files[0] if bayes_files else None
        if bayes_path.exists():
            from engine.bayesian_dc import BayesianDixonColes
            bdc = BayesianDixonColes()
            bdc.load(bayes_path)
            models["bayes_dc"] = bdc
    except Exception:
        pass

    return models


def _load_stacking_model(league):
    """Load the stacking meta-learner for a league, if available."""
    from pathlib import Path
    from models.stacking import StackingEnsemble
    model_dir = Path(__file__).resolve().parent.parent / "models"
    stacking_path = model_dir / f"stacking_{league}.json"
    if stacking_path.exists():
        ens = StackingEnsemble()
        ens.load(stacking_path)
        return ens
    return None


_INTERNAL_TO_STACKING = {
    "dc": "dixon_coles",
    "pr": "poisson_regression",
    "xgb": "xgboost",
    "bayes_dc": "bayes_dc",
    "tw_dc": "tw_dc_stacking",
    "zip": "zip",
    "skellam": "skellam",
}


def get_ensemble_wdl(home_team, away_team, league):
    """
    Get ensemble W/D/L predictions.
    Prefers stacking meta-learner when available, falls back to weighted average.
    Returns dict with home_win, draw, away_win, xg_home, xg_away.
    """
    import time, hashlib, json as _json
    cache_key = hashlib.md5(_json.dumps([home_team, away_team, league]).encode()).hexdigest()
    if cache_key in _ensemble_cache:
        ts, data = _ensemble_cache[cache_key]
        if time.time() - ts < _ENSEMBLE_TTL:
            return data

    models = _load_ensemble_models(league)
    features = compute_match_features(home_team, away_team, league)

    predictions = {}
    xg_h, xg_a = 1.3, 1.1

    # DC (always available)
    try:
        dc = dc_predict(home_team, away_team, league)
        predictions["dc"] = [dc["home_win"], dc["draw"], dc["away_win"]]
        xg_h = dc["exp_home_goals"]
        xg_a = dc["exp_away_goals"]
    except Exception:
        pass

    # Time-Weighted DC (TW-DC)
    if "tw_dc" in models:
        try:
            tw = models["tw_dc"]
            if home_team in tw.teams and away_team in tw.teams:
                tw_probs = tw.get_match_probs(home_team, away_team)
                predictions["tw_dc"] = [tw_probs["home_win"], tw_probs["draw"], tw_probs["away_win"]]
        except Exception:
            pass

    # Bayesian DC (P0-1)
    if "bayes_dc" in models:
        try:
            bdc = models["bayes_dc"]
            if home_team in bdc.teams and away_team in bdc.teams:
                bdc_probs = bdc.get_match_probs(home_team, away_team)
                predictions["bayes_dc"] = [bdc_probs["home_win"], bdc_probs["draw"], bdc_probs["away_win"]]
                # Use Bayesian xG as primary (more robust)
                xg_h = bdc_probs["expected_goals"]["home"]
                xg_a = bdc_probs["expected_goals"]["away"]
        except Exception:
            pass

    # Poisson Regression
    if "poisson" in models:
        try:
            pr_pred = models["poisson"].predict(features)
            predictions["pr"] = [pr_pred["home_win"], pr_pred["draw"], pr_pred["away_win"]]
            xg_h = pr_pred["expected_goals"]["home"]
            xg_a = pr_pred["expected_goals"]["away"]
        except Exception:
            pass

    # XGBoost
    if "xgboost" in models:
        try:
            xgb_pred = models["xgboost"].predict(features)
            predictions["xgb"] = [xgb_pred["home_win"], xgb_pred["draw"], xgb_pred["away_win"]]
        except Exception:
            pass

    # ZIP model (P1-1)
    try:
        from models.zip_model import ZeroInflatedPoisson
        zip_m = ZeroInflatedPoisson()
        # Fit on-the-fly from DC expected goals (pi is league-level)
        zip_m.pi_home = 0.02  # Default, will be overridden by fitted value
        zip_m.pi_away = 0.01
        zip_m.fitted = True
        zip_pred = zip_m.predict_match(xg_h, xg_a)
        predictions["zip"] = [zip_pred["home_win"], zip_pred["draw"], zip_pred["away_win"]]
    except Exception:
        pass

    # Skellam + DC model (P1-2)
    try:
        from models.skellam_model import SkellamModel
        sk_m = SkellamModel()
        # Get rho from DC model
        rho_val = -0.13
        try:
            dc_model = dc_predict(home_team, away_team, league)
            rho_val = dc_model.get("rho", -0.13)
        except:
            pass
        sk_pred = sk_m.predict_with_dc_correction(xg_h, xg_a, rho_val)
        predictions["skellam"] = [sk_pred["home_win"], sk_pred["draw"], sk_pred["away_win"]]
    except Exception:
        pass

    if not predictions:
        result = {"home_win": 0.45, "draw": 0.25, "away_win": 0.30,
                  "xg_home": xg_h, "xg_away": xg_a,
                  "models_used": [], "weights": {}, "method": "fallback"}
        _clean_ensemble_cache()
        _ensemble_cache[cache_key] = (time.time(), result)
        return result

    # --- Try stacking meta-learner first ---
    stacking = _load_stacking_model(league)
    if stacking is not None:
        stacking_preds = {}
        for int_key, pred in predictions.items():
            stack_key = _INTERNAL_TO_STACKING.get(int_key)
            if stack_key and stack_key in stacking.model_names:
                stacking_preds[stack_key] = pred

        if len(stacking_preds) >= 2:
            try:
                final_dict = stacking.predict(stacking_preds)
                result = {
                    "home_win": final_dict["home_win"],
                    "draw": final_dict["draw"],
                    "away_win": final_dict["away_win"],
                    "xg_home": round(float(xg_h), 2),
                    "xg_away": round(float(xg_a), 2),
                    "models_used": list(predictions.keys()),
                    "weights": {k: "stacking" for k in predictions},
                    "method": "stacking",
                }
                _ensemble_cache[cache_key] = (time.time(), result)
                return result
            except Exception:
                pass

    # --- Fallback: manual weighted average ---
    weights = {"dc": 0.10, "tw_dc": 0.10, "bayes_dc": 0.20, "pr": 0.20, "xgb": 0.15, "zip": 0.10, "skellam": 0.15}
    active_weights = {k: weights[k] for k in predictions if k in weights}
    total_w = sum(active_weights.values())
    for k in active_weights:
        active_weights[k] /= total_w

    final = [0.0, 0.0, 0.0]
    for name, pred in predictions.items():
        w = active_weights.get(name, 0)
        for i in range(3):
            final[i] += pred[i] * w

    s = sum(final)
    if s > 0:
        final = [p / s for p in final]

    result = {
        "home_win": round(final[0], 4),
        "draw": round(final[1], 4),
        "away_win": round(final[2], 4),
        "xg_home": round(float(xg_h), 2),
        "xg_away": round(float(xg_a), 2),
        "models_used": list(predictions.keys()),
        "weights": {k: round(v, 3) for k, v in active_weights.items()},
        "method": "weighted_avg",
    }

    _ensemble_cache[cache_key] = (time.time(), result)
    return result

# ============================================================
# 1. Time decay weight: w_t = exp(-alpha * t)
# ============================================================
ALPHA_TIME = 0.5

def time_weight(days_ago, alpha=ALPHA_TIME):
    return math.exp(-alpha * days_ago / 365)


# ============================================================
#  2. Team strength from DC model
# ============================================================
def get_team_params(team, league):
    """Get team attack/defence params from trained DC model."""
    try:
        model = load_model(league)
        att = model.params["attack"].get(team, 0.0)
        deff = model.params["defence"].get(team, 0.0)
        gamma = model.params.get("gamma", 0.2)
        rho = model.params.get("rho", -0.13)
        return att, deff, gamma, rho
    except:
        return 0.0, 0.0, 0.2, -0.13


# ============================================================
# 3. Momentum 鈥?5-match weighted form
# ============================================================
def calc_momentum_v3(team, league):
    """5-match exponentially weighted momentum."""
    try:
        rows = query("""
            SELECT match_date, ftr, home_team, away_team, fthg, ftag
            FROM matches
            WHERE league_code=%s AND (home_team=%s OR away_team=%s)
              AND ftr IS NOT NULL
            ORDER BY match_date DESC LIMIT 5
        """, [league, team, team])
        if not rows:
            return 0.0

        score = 0.0
        total_w = 0.0
        for i, r in enumerate(rows):
            w = math.exp(-0.25 * i)
            is_home = r["home_team"] == team
            gf = r["fthg"] if is_home else r["ftag"]
            ga = r["ftag"] if is_home else r["fthg"]
            gd = gf - ga

            if gd > 0:
                s = 1.0 + min(gd * 0.15, 0.5)
            elif gd == 0:
                s = 0.3
            else:
                s = -0.5 - min(abs(gd) * 0.1, 0.3)

            score += s * w
            total_w += w

        return round(max(min(score / max(total_w, 1), 0.8), -0.8), 3)
    except:
        return 0.0


# ============================================================
# 4. Personnel impact (injuries)
# ============================================================
def calc_personnel_impact(team_name, league):
    """
    # Detect injuries/absences, return scaling factors.
    Returns (att_scale, def_scale) where 1.0 = no impact, <1.0 = weakened.
    """
    try:
        from engine.injury_detector import get_team_injuries
        injuries = get_team_injuries(team_name, league)
        if not injuries or not injuries.get("injured"):
            return 1.0, 1.0

        att_scale = 1.0
        def_scale = 1.0

        for p in injuries["injured"]:
            pos = p.get("position", "")
            impact = p.get("overall", 70) / 100

            if pos in ("Centre-Forward", "Attack"):
                att_scale -= 0.12 * impact
            elif pos in ("Left Winger", "Right Winger"):
                att_scale -= 0.09 * impact
            elif pos in ("Attacking Midfield",):
                att_scale -= 0.07 * impact
            elif pos in ("Central Midfield", "Midfield"):
                att_scale -= 0.04 * impact
                def_scale -= 0.04 * impact
            elif pos in ("Defensive Midfield",):
                def_scale -= 0.07 * impact
            elif pos in ("Centre-Back", "Defender"):
                def_scale -= 0.10 * impact
            elif pos in ("Left-Back", "Right-Back"):
                def_scale -= 0.06 * impact

        return max(att_scale, 0.4), max(def_scale, 0.4)
    except:
        return 1.0, 1.0


# ============================================================
# 5. Tactical indicator
# ============================================================
def _calc_tactical(team, league):
    """Shot accuracy + attack intensity proxy. Returns -0.5 ~ +0.5."""
    try:
        rows = query("""
            SELECT AVG(hst) as avg_hst, AVG(hs) as avg_hs
            FROM matches
            WHERE league_code=%s AND home_team=%s AND hst IS NOT NULL
            
        """, [league, team])
        if not rows or not rows[0]["avg_hst"]:
            return 0.0
        r = rows[0]
        sot_ratio = float(r["avg_hst"] or 0) / max(float(r["avg_hs"] or 1), 1)
        return round((sot_ratio - 0.35) * 2, 2)
    except:
        return 0.0


# ============================================================
# 6. Analysis
# ============================================================
def _analyze_v3(home, away, lam, mu, mom_h, mom_a,
                inj_att_h, inj_def_h, inj_att_a, inj_def_a,
                home_injury, away_injury):
    factors = []

    if lam > mu * 1.4:
        factors.append({"name": "Strength Gap", "icon": "1", "value": f"{home} dominates",
                        "impact": "positive", "detail": f"xG {lam:.1f} vs {mu:.1f}"})
    elif mu > lam * 1.4:
        factors.append({"name": "Strength Gap", "icon": "2", "value": f"{away} dominates",
                        "impact": "negative", "detail": f"xG {lam:.1f} vs {mu:.1f}"})
    else:
        factors.append({"name": "Even Match", "icon": "3", "value": "Evenly matched",
                        "impact": "neutral", "detail": f"xG {lam:.1f} vs {mu:.1f}"})

    factors.append({"name": "Home Advantage", "icon": "4", "value": f"{home} home",
                    "impact": "positive", "detail": "Home advantage included in xG"})

    if abs(mom_h) > 0.2:
        factors.append({"name": f"{home} Form", "icon": "5" if mom_h > 0 else "6",
                        "value": "Hot" if mom_h > 0.2 else "Cold",
                        "impact": "positive" if mom_h > 0 else "negative",
                        "detail": f"5-match momentum: {mom_h:+.2f}"})
    if abs(mom_a) > 0.2:
        factors.append({"name": f"{away} Form", "icon": "5" if mom_a > 0 else "6",
                        "value": "Hot" if mom_a > 0.2 else "Cold",
                        "impact": "positive" if mom_a < 0 else "negative",
                        "detail": f"5-match momentum: {mom_a:+.2f}"})

    if inj_att_h < 0.95 or inj_def_h < 0.95:
        pct = round((1 - (inj_att_h + inj_def_h) / 2) * 100)
        factors.append({"name": f"{home} Injuries", "icon": "7", "value": f"-{pct}%",
                        "impact": "negative",
                        "detail": f"ATK {inj_att_h:.0%} DEF {inj_def_h:.0%}"})
    if inj_att_a < 0.95 or inj_def_a < 0.95:
        pct = round((1 - (inj_att_a + inj_def_a) / 2) * 100)
        factors.append({"name": f"{away} Injuries", "icon": "7", "value": f"-{pct}%",
                        "impact": "positive",
                        "detail": f"ATK {inj_att_a:.0%} DEF {inj_def_a:.0%}"})

    total_expected = lam + mu
    if total_expected > 3.0:
        factors.append({"name": "Goal Expectation", "icon": "8", "value": "High scoring",
                        "impact": "neutral", "detail": f"Total xG {total_expected:.1f} > 3.0"})
    elif total_expected < 2.0:
        factors.append({"name": "Goal Expectation", "icon": "9", "value": "Low scoring",
                        "impact": "neutral", "detail": f"Total xG {total_expected:.1f} < 2.0"})

    return factors[:8]


def _get_team_players(team_name):
    clubs = search_club(team_name, 3)
    if not clubs:
        return []
    return get_club_squad_rated(clubs[0]["club_id"])


def _top_players(players, n=3):
    return sorted(players, key=lambda p: p.get("overall", 0), reverse=True)[:n]


# ============================================================
# 7. Main prediction function (FIXED)
# ============================================================
def full_prediction_v3(home_team, away_team, league="E0", simulations=2000):
    """
    # Full prediction with correct DC formula.

    Key fix: lambda/mu calculated using proper DC formula,
    # then adjusted multiplicatively for injuries/momentum/tactics.
    """
    t0 = time.time()

    # === DC model parameters ===
    att_h, def_h, gamma, rho = get_team_params(home_team, league)
    att_a, def_a, _, _ = get_team_params(away_team, league)

    # === Base expected goals (correct DC formula) ===
    # lambda = exp(alpha_home + beta_away + gamma)
    # mu = exp(alpha_away + beta_home)
    base_lam = math.exp(att_h + def_a + gamma)
    base_mu = math.exp(att_a + def_h)

    # === Momentum ===
    mom_h = calc_momentum_v3(home_team, league)
    mom_a = calc_momentum_v3(away_team, league)

    # === Personnel impact (multiplicative on expected goals) ===
    inj_att_h, inj_def_h = calc_personnel_impact(home_team, league)
    inj_att_a, inj_def_a = calc_personnel_impact(away_team, league)

    # === Tactical indicator ===
    tact_h = _calc_tactical(home_team, league)
    tact_a = _calc_tactical(away_team, league)

    # Final lambda/mu with adjustments.
    # Injury: multiplicative on own attack, gentle additive on opponent defence weakness.
    #   defence_weakness_factor = 1 + (1 - inj_def) * 0.3
    #   e.g. inj_def=0.6 -> factor=1.12 (12% boost, not 67% as with 1/0.6)
    def_def_weakness_h = 1 + (1 - inj_def_a) * 0.3  # home benefits from away defence injuries
    def_def_weakness_a = 1 + (1 - inj_def_h) * 0.3  # away benefits from home defence injuries

    lam = base_lam * inj_att_h * def_def_weakness_h * (1 + mom_h * 0.20) * (1 + tact_h * 0.08)
    mu = base_mu * inj_att_a * def_def_weakness_a * (1 + mom_a * 0.15) * (1 + tact_a * 0.06)

    # Clamp to reasonable range
    lam = max(lam, 0.15)
    mu = max(mu, 0.10)

    # Get ensemble W/D/L (best probability estimate)
    try:
        ens = get_ensemble_wdl(home_team, away_team, league)
    except Exception:
        ens = None

    # Monte Carlo simulation with tau correction
    sim = MonteCarloSimulator(home_gamma=0.0, rho=rho)  # gamma already in base_lam
    # Build custom squads with pre-calculated strength
    #  We bypass squad_strength and directly simulate with lam/mu
    from engine.dixon_coles import DixonColes
    from scipy.stats import poisson as sp_poisson

    dc = DixonColes()
    n = simulations
    prob_matrix = dc._build_prob_matrix_with_params(lam, mu, rho) if hasattr(dc, '_build_prob_matrix_with_params') else None

    if prob_matrix is None:
        # Fallback: build matrix directly
        max_goals = 10
        gn = max_goals + 1
        prob_matrix = np.zeros((gn, gn))
        for i in range(gn):
            for j in range(gn):
                p = sp_poisson.pmf(i, lam) * sp_poisson.pmf(j, mu)
                tau = dc.rho_correction(i, j, lam, mu, rho)
                prob_matrix[i, j] = max(tau * p, 0)
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total

    #  Sample from joint distribution
    flat = prob_matrix.flatten()
    flat = np.maximum(flat, 0)
    flat /= flat.sum()
    grid_size = prob_matrix.shape[0]

    indices = np.random.choice(len(flat), size=n, p=flat)
    hg = indices // grid_size
    ag = indices % grid_size

    # === W/D/L from ensemble (best probability estimate) ===
    if ens is not None:
        wdl = {
            "home_win": ens["home_win"],
            "draw": ens["draw"],
            "away_win": ens["away_win"],
        }
    else:
        # Fallback: use simulation-based WDL
        results = ["H" if h > a else "A" if a > h else "D" for h, a in zip(hg, ag)]
        wdl = {
            "home_win": round(results.count("H") / n, 4),
            "draw": round(results.count("D") / n, 4),
            "away_win": round(results.count("A") / n, 4),
        }

    # === Score distribution ===
    scores = [f"{int(h)}-{int(a)}" for h, a in zip(hg, ag)]
    sc = Counter(scores)
    score_dist = {s: round(c / n, 4) for s, c in sc.most_common(20)}
    most_likely = max(sc, key=sc.get) if sc else "0-0"

    # === Over/Under ===
    total_goals = hg + ag
    over25 = round(float(np.mean(total_goals > 2.5)), 4)
    under25 = round(1 - over25, 4)

    # === Key players ===
    home_players = _get_team_players(home_team)
    away_players = _get_team_players(away_team)
    key_home = _top_players(home_players, 3)
    key_away = _top_players(away_players, 3)

    # === Injury details ===
    try:
        from engine.injury_detector import get_team_injuries
        home_injury = get_team_injuries(home_team, league)
        away_injury = get_team_injuries(away_team, league)
    except:
        home_injury = away_injury = None

    # === Factor analysis ===
    factors = _analyze_v3(home_team, away_team, lam, mu, mom_h, mom_a,
                          inj_att_h, inj_def_h, inj_att_a, inj_def_a,
                          home_injury, away_injury)

    elapsed = round((time.time() - t0) * 1000)

    return {
        "home_team": home_team, "away_team": away_team, "league": league,
        "model_version": "v7-zip-skellam",
        "ensemble": ens if 'ens' in dir() and ens else None,
        "expected_goals": {"home": round(float(lam), 2), "away": round(float(mu), 2)},
        "wdl": wdl,
        "avg_goals": {
            "home": round(float(np.mean(hg)), 2),
            "away": round(float(np.mean(ag)), 2),
            "total": round(float(np.mean(total_goals)), 2),
        },
        "over_under": {"over_2_5": over25, "under_2_5": under25},
        "score_distribution": score_dist,
        "most_likely_score": most_likely,
        "top_5_scores": [{"score": s, "probability": p} for s, p in list(score_dist.items())[:5]],
        "key_players": {"home": key_home, "away": key_away},
        "injuries": {"home": home_injury, "away": away_injury},
        "factors": factors,
        "parameters": {
            "base_lam": round(float(base_lam), 3), "base_mu": round(float(base_mu), 3),
            "lam": round(float(lam), 2), "mu": round(float(mu), 2),
            "rho": round(float(rho), 4), "gamma": round(float(gamma), 4),
            "momentum_home": mom_h, "momentum_away": mom_a,
            "tactical_home": tact_h, "tactical_away": tact_a,
            "injury_home_att": round(inj_att_h, 3), "injury_home_def": round(inj_def_h, 3),
            "injury_away_att": round(inj_att_a, 3), "injury_away_def": round(inj_def_a, 3),
        },
        "simulations": simulations,
        "duration_ms": elapsed,
    }



def _cl_full_prediction(home_team, away_team, simulations=2000):
    """CL prediction: delegates probabilities to predict._cl_predict, adds MC score distribution."""
    from api.predict import _cl_predict
    from scipy.stats import poisson as sp_poisson
    from engine.dixon_coles import DixonColes

    t0 = time.time()

    # Reuse the shared CL probability/xG computation
    base = _cl_predict(home_team, away_team)
    lam = base["exp_home_goals"]
    mu = base["exp_away_goals"]

    # Monte Carlo for score distribution (tau-corrected)
    dc = DixonColes()
    rho = -0.13
    max_goals = 10
    gn = max_goals + 1
    prob_matrix = np.zeros((gn, gn))
    for i in range(gn):
        for j in range(gn):
            p = sp_poisson.pmf(i, lam) * sp_poisson.pmf(j, mu)
            tau = dc.rho_correction(i, j, lam, mu, rho)
            prob_matrix[i, j] = max(tau * p, 0)
    total = prob_matrix.sum()
    if total > 0:
        prob_matrix /= total

    flat = prob_matrix.flatten()
    flat = np.maximum(flat, 0)
    flat /= flat.sum()
    indices = np.random.choice(len(flat), size=simulations, p=flat)
    hg = indices // gn
    ag = indices % gn

    scores = [f"{int(h)}-{int(a)}" for h, a in zip(hg, ag)]
    sc = Counter(scores)
    score_dist = {s: round(c / simulations, 4) for s, c in sc.most_common(20)}
    most_likely = max(sc, key=sc.get) if sc else "0-0"

    total_goals = hg + ag
    over25 = round(float(np.mean(total_goals > 2.5)), 4)
    elapsed = round((time.time() - t0) * 1000)

    return {
        "home_team": home_team, "away_team": away_team, "league": "CL",
        "model_version": "cl-cross-league",
        "expected_goals": {"home": round(float(lam), 2), "away": round(float(mu), 2)},
        "wdl": {
            "home_win": base["home_win"],
            "draw": base["draw"],
            "away_win": base["away_win"],
        },
        "avg_goals": {
            "home": round(float(np.mean(hg)), 2),
            "away": round(float(np.mean(ag)), 2),
            "total": round(float(np.mean(total_goals)), 2),
        },
        "over_under": {"over_2_5": over25, "under_2_5": round(1 - over25, 4)},
        "score_distribution": score_dist,
        "most_likely_score": most_likely,
        "top_5_scores": [{"score": s, "probability": p} for s, p in list(score_dist.items())[:5]],
        "key_players": {"home": [], "away": []},
        "injuries": {"home": None, "away": None},
        "factors": {"model": base["model"]},
        "parameters": {"lam": round(float(lam), 2), "mu": round(float(mu), 2)},
        "simulations": simulations,
        "duration_ms": elapsed,
    }
