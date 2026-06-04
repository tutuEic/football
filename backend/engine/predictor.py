# -*- coding: utf-8 -*-
"""
Dixon-Coles predictor - fast mode.
Predicts using pre-trained model parameters directly, without Monte Carlo.
"""
import json
import os

from engine.dixon_coles import DixonColes
from config import MODEL_DIR

os.makedirs(MODEL_DIR, exist_ok=True)


def load_model(league_code):
    """Load the latest trained model for a given league."""
    models = [
        f for f in os.listdir(MODEL_DIR)
        if f.startswith(f"dc_{league_code}_") and f.endswith(".json")
    ]
    if not models:
        raise FileNotFoundError(
            f"No trained model for league '{league_code}'. "
            f"Run train_league('{league_code}') first."
        )

    latest = sorted(models)[-1]
    with open(os.path.join(MODEL_DIR, latest), "r", encoding="utf-8") as f:
        data = json.load(f)

    model = DixonColes()
    model.teams = data["teams"]
    model.params = data["params"]
    model.fitted = True
    return model


def predict_match(home_team, away_team, league_code="E0"):
    """Quick predict a single match using the trained Dixon-Coles model."""
    model = load_model(league_code)

    if home_team not in model.teams:
        raise ValueError(f"Unknown team: '{home_team}'. Available: {model.teams[:10]}...")
    if away_team not in model.teams:
        raise ValueError(f"Unknown team: '{away_team}'. Available: {model.teams[:10]}...")

    probs = model.get_match_probs(home_team, away_team)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "league": league_code,
        "home_win": round(probs["home_win"], 4),
        "draw": round(probs["draw"], 4),
        "away_win": round(probs["away_win"], 4),
        "exp_home_goals": round(probs["expected_goals"]["home"], 2),
        "exp_away_goals": round(probs["expected_goals"]["away"], 2),
    }


def list_available_models():
    """List all trained models."""
    if not os.path.exists(MODEL_DIR):
        return []
    models = []
    for f in os.listdir(MODEL_DIR):
        if f.endswith(".json"):
            parts = f.replace(".json", "").split("_")
            models.append({
                "file": f,
                "league": parts[1] if len(parts) > 1 else "?",
                "season": parts[2] if len(parts) > 2 else "?",
            })
    return models



# ============================================================
# Probability Calibration (Platt-style binning)
# ============================================================
import numpy as _np

_calibration_data = None

def _load_calibration_data():
    """Load or compute calibration mapping from historical predictions."""
    global _calibration_data
    if _calibration_data is not None:
        return _calibration_data

    from data.mysql_client import query
    # Get completed matches with DC model predictions
    rows = query("""
        SELECT home_team, away_team, league_code, fthg, ftag, ftr
        FROM matches
        WHERE fthg IS NOT NULL AND ftr IS NOT NULL
        ORDER BY match_date DESC LIMIT 2000
    """)

    if not rows or len(rows) < 100:
        _calibration_data = None
        return None

    # Compute predictions for each match
    predictions = []
    for r in rows:
        try:
            model = load_model(r['league_code'])
            probs = model.get_match_probs(r['home_team'], r['away_team'])
            actual = r['ftr']
            if actual not in ('H', 'D', 'A'):
                continue
            for outcome, key in [('H', 'home_win'), ('D', 'draw'), ('A', 'away_win')]:
                predictions.append({
                    'predicted': probs[key],
                    'actual': 1.0 if actual == outcome else 0.0,
                })
        except Exception:
            continue

    if len(predictions) < 50:
        _calibration_data = None
        return None

    # Build calibration curve using equal-frequency binning
    preds = sorted(predictions, key=lambda x: x['predicted'])
    n_bins = 10
    bin_size = len(preds) // n_bins
    calibration_map = []

    for i in range(n_bins):
        start = i * bin_size
        end = start + bin_size if i < n_bins - 1 else len(preds)
        chunk = preds[start:end]
        avg_pred = _np.mean([p['predicted'] for p in chunk])
        avg_actual = _np.mean([p['actual'] for p in chunk])
        calibration_map.append({
            'predicted_center': round(float(avg_pred), 4),
            'actual_freq': round(float(avg_actual), 4),
            'count': len(chunk),
        })

    _calibration_data = calibration_map
    return calibration_map


def calibrate_prob(prob, cal_map=None):
    """Apply calibration to a single probability using linear interpolation."""
    if cal_map is None:
        cal_map = _load_calibration_data()
    if cal_map is None or len(cal_map) < 2:
        return prob

    # Interpolate
    centers = [b['predicted_center'] for b in cal_map]
    actuals = [b['actual_freq'] for b in cal_map]

    # Clamp to range
    if prob <= centers[0]:
        return actuals[0]
    if prob >= centers[-1]:
        return actuals[-1]

    # Linear interpolation
    for i in range(len(centers) - 1):
        if centers[i] <= prob <= centers[i + 1]:
            t = (prob - centers[i]) / (centers[i + 1] - centers[i])
            return actuals[i] + t * (actuals[i + 1] - actuals[i])

    return prob


def calibrate_wdl(result_dict, key_prefix=''):
    """Calibrate W/D/L probabilities in a prediction result dict."""
    cal_map = _load_calibration_data()
    if cal_map is None:
        return result_dict

    hw = calibrate_prob(result_dict.get('home_win', 0.33), cal_map)
    d = calibrate_prob(result_dict.get('draw', 0.33), cal_map)
    aw = calibrate_prob(result_dict.get('away_win', 0.33), cal_map)

    # Renormalize
    total = hw + d + aw
    if total > 0:
        hw /= total
        d /= total
        aw /= total

    result_dict['home_win'] = round(hw, 4)
    result_dict['draw'] = round(d, 4)
    result_dict['away_win'] = round(aw, 4)
    result_dict['calibrated'] = True

    return result_dict


def get_calibration_info():
    """Return the calibration curve for inspection."""
    cal_map = _load_calibration_data()
    if cal_map is None:
        return {"status": "no_data", "note": "Not enough historical data to compute calibration"}
    return {
        "status": "ok",
        "bins": len(cal_map),
        "data": cal_map,
    }
