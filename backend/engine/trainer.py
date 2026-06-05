"""Dixon-Coles model training."""
import json, os
from engine.dixon_coles import DixonColes
from config import MODEL_DIR
from data.match_repo import get_matches_for_training, get_seasons

os.makedirs(MODEL_DIR, exist_ok=True)

# Maximum matches used for training.  Override with TRAIN_MAX_MATCHES env var.
MAX_TRAINING_MATCHES = int(os.getenv("TRAIN_MAX_MATCHES", "2000"))


def train_league(league_code, seasons=None, model_type="dixon_coles"):
    """Train a Dixon-Coles model for one league."""
    if seasons is None:
        all_seasons = get_seasons(league_code)
        if not all_seasons:
            raise ValueError(f"No data for league '{league_code}'")
        seasons = all_seasons[-2:] if len(all_seasons) >= 2 else all_seasons
        print(f"Auto-selected seasons: {seasons}")

    matches = get_matches_for_training(league_code, seasons)
    
    # Cap to the most recent N matches to keep training tractable.
    # Default raised from 500 to 2000; override via TRAIN_MAX_MATCHES env var.
    if len(matches) > MAX_TRAINING_MATCHES:
        total_available = len(matches)
        matches = matches[-MAX_TRAINING_MATCHES:]
        print(f"Using last {MAX_TRAINING_MATCHES} matches (of {total_available} available)")
    if len(matches) < 30:
        raise ValueError(
            f"Not enough data: {len(matches)} matches for {league_code} "
            f"(need at least 30)"
        )

    print(f"Training on {len(matches)} matches, {seasons}")

    model = DixonColes()
    success = model.fit(matches)

    if not success:
        raise RuntimeError(f"Training failed for {league_code}")

    # Validate parameters
    rho = model.params.get("rho", 0)
    if abs(rho) > 0.5:
        print(f"Warning: rho={rho:.4f} is extreme, model may be unreliable")
    gamma = model.params.get("gamma", 0)
    if abs(gamma) > 1.0:
        print(f"Warning: gamma={gamma:.4f} is extreme")
    ll = model.params.get("log_likelihood", 0)
    if ll == 0:
        print("Warning: log-likelihood is 0, model may not have converged")

    model_file = os.path.join(
        MODEL_DIR, f"dc_{league_code}_{seasons[-1]}.json"
    )
    with open(model_file, 'w', encoding='utf-8') as f:
        json.dump({
            "league": league_code,
            "seasons": seasons,
            "model_type": model_type,
            "teams": model.teams,
            "params": {
                k: v if isinstance(v, dict) else float(v)
                for k, v in model.params.items()
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"Model saved -> {model_file}")
    print(f"  Teams: {len(model.teams)}")
    print(f"  LL: {model.params['log_likelihood']:.2f}")
    print(f"  rho: {model.params['rho']:.4f}")
    print(f"  gamma: {model.params['gamma']:.4f}")

    return model, model_file


def train_all_leagues():
    """Train all leagues with sufficient data."""
    from data.match_repo import get_all_leagues
    leagues = get_all_leagues()
    results = {}
    for lc in leagues:
        try:
            model, f = train_league(lc)
            results[lc] = {"status": "ok", "file": f}
        except Exception as e:
            results[lc] = {"status": "error", "error": str(e)}
    return results




def train_weighted_league(league_code, seasons=None, alpha=0.5):
    """Train DC model with exponential time-decay weights.
    
    Args:
        alpha: decay rate. Higher = faster decay.
               alpha=0.5 means a match 1 year ago has weight exp(-0.5) = 0.61
               alpha=1.0 means a match 1 year ago has weight exp(-1.0) = 0.37
    """
    import math
    from datetime import datetime, date

    if seasons is None:
        all_seasons = get_seasons(league_code)
        if not all_seasons:
            raise ValueError(f"No data for league '{league_code}'")
        seasons = all_seasons[-2:] if len(all_seasons) >= 2 else all_seasons

    matches = get_matches_for_training(league_code, seasons)
    if len(matches) < 30:
        raise ValueError(f"Not enough data: {len(matches)} matches")

    # For time-weighted training, we need match dates
    # Re-fetch with dates included
    from data.mysql_client import query
    placeholders = ','.join(['%s'] * len(seasons))
    dated_matches = query(f"""
        SELECT home_team AS home, away_team AS away,
               fthg AS home_goals, ftag AS away_goals, match_date
        FROM matches
        WHERE league_code=%s AND season IN ({placeholders})
          AND fthg IS NOT NULL AND ftag IS NOT NULL
    """, [league_code] + list(seasons))

    if not dated_matches:
        raise ValueError("No dated matches found")

    today = date.today()
    weighted = []
    for m in dated_matches:
        md = m.get('match_date')
        if md:
            if isinstance(md, str):
                md = datetime.strptime(md, '%Y-%m-%d').date()
            days_ago = (today - md).days
        else:
            days_ago = 180  # default: 6 months ago
        weight = math.exp(-alpha * days_ago / 365)
        weighted.append({
            'home': m['home'], 'away': m['away'],
            'home_goals': m['home_goals'], 'away_goals': m['away_goals'],
            'weight': round(weight, 4),
        })

    if len(weighted) > MAX_TRAINING_MATCHES:
        weighted = weighted[-MAX_TRAINING_MATCHES:]

    model = DixonColes()
    model.fit(weighted)

    # Save with alpha in filename
    model_file = os.path.join(MODEL_DIR, f"dc_{league_code}_{seasons[-1]}_tw.json")
    with open(model_file, 'w', encoding='utf-8') as f:
        json.dump({
            "league": league_code, "seasons": seasons,
            "model_type": "time_weighted",
            "alpha": alpha,
            "teams": model.teams,
            "params": {k: v if isinstance(v, dict) else float(v) for k, v in model.params.items()},
        }, f, indent=2, ensure_ascii=False)

    print(f"Time-weighted model saved -> {model_file}")
    print(f"  alpha={alpha}, matches={len(weighted)}, teams={len(model.teams)}")
    return model, model_file


def train_bayesian_league(league_code, seasons=None, alpha=0.7):
    """Train Bayesian DC model with time-decay weights.
    
    Args:
        alpha: time decay rate (0.7 = match 1 year ago has weight 0.50)
    """
    import math
    from datetime import datetime, date
    from engine.bayesian_dc import BayesianDixonColes
    from data.mysql_client import query
    
    if seasons is None:
        all_seasons = get_seasons(league_code)
        if not all_seasons:
            raise ValueError(f"No data for league '{league_code}'")
        seasons = all_seasons[-3:] if len(all_seasons) >= 3 else all_seasons

    placeholders = ",".join(["%s"] * len(seasons))
    dated = query(f"""
        SELECT home_team AS home, away_team AS away,
               fthg AS home_goals, ftag AS away_goals, match_date
        FROM matches
        WHERE league_code=%s AND season IN ({placeholders})
          AND fthg IS NOT NULL AND ftag IS NOT NULL
        ORDER BY match_date
    """, [league_code] + list(seasons))

    if not dated or len(dated) < 30:
        raise ValueError(f"Not enough data: {len(dated or [])} matches for {league_code}")

    today = date.today()
    weighted = []
    for m in dated:
        md = m["match_date"]
        if isinstance(md, str):
            md = datetime.strptime(md, "%Y-%m-%d").date()
        days_ago = (today - md).days
        w = math.exp(-alpha * days_ago / 365)
        weighted.append({
            "home": m["home"], "away": m["away"],
            "home_goals": m["home_goals"], "away_goals": m["away_goals"],
            "weight": round(w, 4),
        })

    if len(weighted) > MAX_TRAINING_MATCHES:
        weighted = weighted[-MAX_TRAINING_MATCHES:]

    print(f"Training Bayesian DC-TW for {league_code}: {len(weighted)} matches, alpha={alpha}")
    model = BayesianDixonColes()
    model.fit(weighted)

    model_file = os.path.join(MODEL_DIR, f"bayes_dc_{league_code}_{seasons[-1]}.json")
    model.save(model_file)

    print(f"Bayesian model saved -> {model_file}")
    print(f"  gamma={model.params['gamma']:.4f} +/- {model.params['gamma_std']:.4f}")
    print(f"  rho={model.params['rho']:.4f} +/- {model.params['rho_std']:.4f}")
    return model, model_file
