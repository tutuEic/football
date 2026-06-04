# -*- coding: utf-8 -*-
"""
Training Pipeline — orchestrates feature computation, model training, and evaluation.
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.match_repo import get_matches_for_training, get_seasons
from features.feature_store import compute_match_features, FEATURE_NAMES
from features.elo import EloSystem
from models.poisson_regression import PoissonRegression
from models.registry import ModelRegistry
import numpy as np


def prepare_dataset(league_code: str, seasons: list[str] = None):
    """
    Prepare training dataset with features.

    Returns: X (features), y_home (home goals), y_away (away goals), matches
    """
    if seasons is None:
        all_s = get_seasons(league_code)
        seasons = sorted(all_s)[-3:] if len(all_s) >= 3 else all_s

    matches = get_matches_for_training(league_code, seasons)
    print(f"Preparing dataset: {len(matches)} matches from {seasons}")

    # Build Elo first
    elo = EloSystem()
    elo.build_from_history(league_code, seasons)

    # Compute features for each match
    X = []
    y_home = []
    y_away = []
    valid_matches = []

    for i, m in enumerate(matches):
        try:
            features = compute_match_features(m["home"], m["away"], league_code)
            x = [features.get(f, 0) for f in FEATURE_NAMES]
            X.append(x)
            y_home.append(int(m["home_goals"]))
            y_away.append(int(m["away_goals"]))
            valid_matches.append(m)
        except Exception as e:
            continue

        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(matches)} matches...")

    X = np.array(X)
    y_home = np.array(y_home)
    y_away = np.array(y_away)

    print(f"Dataset ready: {X.shape[0]} samples, {X.shape[1]} features")
    return X, y_home, y_away, valid_matches


def train_test_split(X, y_home, y_away, matches, test_ratio=0.15, val_ratio=0.15):
    """Split dataset into train/val/test (temporal split)."""
    n = len(X)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    n_train = n - n_test - n_val

    # Temporal split: oldest -> train, middle -> val, newest -> test
    X_train, yh_train, ya_train = X[:n_train], y_home[:n_train], y_away[:n_train]
    X_val, yh_val, ya_val = X[n_train:n_train+n_val], y_home[n_train:n_train+n_val], y_away[n_train:n_train+n_val]
    X_test, yh_test, ya_test = X[n_train+n_val:], y_home[n_train+n_val:], y_away[n_train+n_val:]

    print(f"Split: train={n_train}, val={n_val}, test={n_test}")
    return (X_train, yh_train, ya_train), (X_val, yh_val, ya_val), (X_test, yh_test, ya_test)


def train_poisson_regression(league_code: str, seasons: list[str] = None):
    """Train Poisson regression model for a league."""
    print(f"\n{'='*60}")
    print(f"Training Poisson Regression for {league_code}")
    print(f"{'='*60}")

    # Prepare data
    X, y_home, y_away, matches = prepare_dataset(league_code, seasons)
    train, val, test = train_test_split(X, y_home, y_away, matches)

    # Train
    model = PoissonRegression()
    model.fit(train[0], train[1], train[2])

    # Evaluate on validation set
    val_metrics = evaluate_model(model, val[0], val[1], val[2], matches[len(train[0]):len(train[0])+len(val[0])])

    # Evaluate on test set
    test_metrics = evaluate_model(model, test[0], test[1], test[2], matches[len(train[0])+len(val[0]):])

    # Save model
    model_dir = Path(__file__).resolve().parent.parent / 'models'
    model_path = model_dir / f'poisson_{league_code}.json'
    model.save(model_path)

    # Register
    registry = ModelRegistry()
    registry.register_model(
        'poisson', league_code, model_path.name,
        metrics={"val": val_metrics, "test": test_metrics},
        metadata={"seasons": seasons, "n_features": model.n_features}
    )

    print(f"\nModel saved to {model_path}")
    print(f"Val metrics:  acc={val_metrics['accuracy']:.3f}, brier={val_metrics['brier']:.4f}")
    print(f"Test metrics: acc={test_metrics['accuracy']:.3f}, brier={test_metrics['brier']:.4f}")

    return model, val_metrics, test_metrics


def evaluate_model(model, X, y_home, y_away, matches=None):
    """Evaluate model on a dataset."""
    correct = 0
    brier_sum = 0
    n = len(X)

    for i in range(n):
        features_dict = dict(zip(FEATURE_NAMES, X[i]))
        pred = model.predict(features_dict)

        hg, ag = int(y_home[i]), int(y_away[i])
        actual = "H" if hg > ag else ("A" if ag > hg else "D")
        predicted = max({"H": pred["home_win"], "D": pred["draw"], "A": pred["away_win"]},
                       key=lambda k: {"H": pred["home_win"], "D": pred["draw"], "A": pred["away_win"]}[k])

        if predicted == actual:
            correct += 1

        brier_sum += (pred["home_win"] - (1 if actual == "H" else 0)) ** 2
        brier_sum += (pred["draw"] - (1 if actual == "D" else 0)) ** 2
        brier_sum += (pred["away_win"] - (1 if actual == "A" else 0)) ** 2

    accuracy = correct / n
    brier = brier_sum / (n * 3)

    return {
        "accuracy": round(accuracy, 4),
        "brier": round(brier, 4),
        "n_samples": n,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--league", default="E0")
    args = p.parse_args()

    train_poisson_regression(args.league)


def train_xgboost(league_code: str, seasons: list[str] = None):
    """Train XGBoost model for a league."""
    print(f"\n{'='*60}")
    print(f"Training XGBoost for {league_code}")
    print(f"{'='*60}")

    from models.xgboost_model import XGBoostPredictor
    X, y_home, y_away, matches = prepare_dataset(league_code, seasons)
    train, val, test = train_test_split(X, y_home, y_away, matches)

    model = XGBoostPredictor()
    model.fit(train[0], train[1], train[2], val[0], val[1], val[2])

    val_metrics = evaluate_xgb(model, val[0], val[1], val[2])
    test_metrics = evaluate_xgb(model, test[0], test[1], test[2])

    model_dir = Path(__file__).resolve().parent.parent / 'models'
    model_path = model_dir / f'xgboost_{league_code}.json'
    model.save(model_path)

    registry = ModelRegistry()
    registry.register_model('xgboost', league_code, model_path.name,
                           metrics={"val": val_metrics, "test": test_metrics})

    print(f"Val metrics:  acc={val_metrics['accuracy']:.3f}, brier={val_metrics['brier']:.4f}")
    print(f"Test metrics: acc={test_metrics['accuracy']:.3f}, brier={test_metrics['brier']:.4f}")

    # Feature importance
    importance = model.get_feature_importance()
    print(f"\nTop 10 features:")
    for feat, score in list(importance.items())[:10]:
        print(f"  {feat}: {score:.1f}")

    return model, val_metrics, test_metrics


def evaluate_xgb(model, X, y_home, y_away):
    """Evaluate XGBoost model."""
    from features.feature_store import FEATURE_NAMES
    correct = 0
    brier_sum = 0
    n = len(X)

    for i in range(n):
        features = dict(zip(FEATURE_NAMES, X[i]))
        pred = model.predict(features)
        hg, ag = int(y_home[i]), int(y_away[i])
        actual = "H" if hg > ag else ("A" if ag > hg else "D")
        outcomes = {"H": pred["home_win"], "D": pred["draw"], "A": pred["away_win"]}
        predicted = max(outcomes, key=outcomes.get)

        if predicted == actual:
            correct += 1

        brier_sum += (pred["home_win"] - (1 if actual == "H" else 0)) ** 2
        brier_sum += (pred["draw"] - (1 if actual == "D" else 0)) ** 2
        brier_sum += (pred["away_win"] - (1 if actual == "A" else 0)) ** 2

    return {"accuracy": round(correct / n, 4), "brier": round(brier_sum / (n * 3), 4), "n_samples": n}


def train_stacking(league_code: str, seasons: list[str] = None):
    """Train stacking ensemble on base model predictions."""
    print(f"\n{'='*60}")
    print(f"Training Stacking Ensemble for {league_code}")
    print(f"{'='*60}")

    from models.poisson_regression import PoissonRegression
    from models.xgboost_model import XGBoostPredictor
    from models.stacking import StackingEnsemble
    from features.feature_store import FEATURE_NAMES

    X, y_home, y_away, matches = prepare_dataset(league_code, seasons)
    train, val, test = train_test_split(X, y_home, y_away, matches)

    # Load trained base models
    model_dir = Path(__file__).resolve().parent.parent / 'models'

    # Poisson Regression
    pr = PoissonRegression()
    pr_path = model_dir / f'poisson_{league_code}.json'
    if pr_path.exists():
        pr.load(pr_path)
    else:
        print("Training Poisson Regression first...")
        pr.fit(train[0], train[1], train[2])

    # XGBoost
    xgb_model = XGBoostPredictor()
    xgb_path = model_dir / f'xgboost_{league_code}.json'
    if xgb_path.exists():
        xgb_model.load(xgb_path)
    else:
        print("Training XGBoost first...")
        xgb_model.fit(train[0], train[1], train[2], val[0], val[1], val[2])

    # Generate base predictions on validation set
    base_preds = {"dixon_coles": [], "poisson_regression": [], "xgboost": []}
    n_val = len(val[0])

    from engine.predictor import predict_match as dc_predict
    for i in range(n_val):
        features = dict(zip(FEATURE_NAMES, val[0][i]))
        m = matches[len(train[0]) + i]

        # DC
        try:
            dc = dc_predict(m["home"], m["away"], league_code)
            base_preds["dixon_coles"].append([dc["home_win"], dc["draw"], dc["away_win"]])
        except:
            base_preds["dixon_coles"].append([0.45, 0.25, 0.30])

        # Poisson Regression
        try:
            pr_pred = pr.predict(features)
            base_preds["poisson_regression"].append([pr_pred["home_win"], pr_pred["draw"], pr_pred["away_win"]])
        except:
            base_preds["poisson_regression"].append([0.45, 0.25, 0.30])

        # XGBoost
        try:
            xgb_pred = xgb_model.predict(features)
            base_preds["xgboost"].append([xgb_pred["home_win"], xgb_pred["draw"], xgb_pred["away_win"]])
        except:
            base_preds["xgboost"].append([0.45, 0.25, 0.30])

    # Convert to numpy arrays
    for k in base_preds:
        base_preds[k] = np.array(base_preds[k])

    # Train stacking
    ensemble = StackingEnsemble()
    ensemble.fit(base_preds, val[1], val[2])

    # Evaluate on test set
    test_preds = {"dixon_coles": [], "poisson_regression": [], "xgboost": []}
    n_test = len(test[0])
    for i in range(n_test):
        features = dict(zip(FEATURE_NAMES, test[0][i]))
        m = matches[len(train[0]) + len(val[0]) + i]

        try:
            dc = dc_predict(m["home"], m["away"], league_code)
            test_preds["dixon_coles"].append([dc["home_win"], dc["draw"], dc["away_win"]])
        except:
            test_preds["dixon_coles"].append([0.45, 0.25, 0.30])

        try:
            pr_pred = pr.predict(features)
            test_preds["poisson_regression"].append([pr_pred["home_win"], pr_pred["draw"], pr_pred["away_win"]])
        except:
            test_preds["poisson_regression"].append([0.45, 0.25, 0.30])

        try:
            xgb_pred = xgb_model.predict(features)
            test_preds["xgboost"].append([xgb_pred["home_win"], xgb_pred["draw"], xgb_pred["away_win"]])
        except:
            test_preds["xgboost"].append([0.45, 0.25, 0.30])

    for k in test_preds:
        test_preds[k] = np.array(test_preds[k])

    # Evaluate ensemble
    correct = 0
    brier_sum = 0
    for i in range(n_test):
        base = {k: v[i] for k, v in test_preds.items()}
        final = ensemble.predict(base)
        hg, ag = int(test[1][i]), int(test[2][i])
        actual = "H" if hg > ag else ("A" if ag > hg else "D")
        outcomes = {"H": final["home_win"], "D": final["draw"], "A": final["away_win"]}
        predicted = max(outcomes, key=outcomes.get)
        if predicted == actual:
            correct += 1
        brier_sum += (final["home_win"] - (1 if actual == "H" else 0)) ** 2
        brier_sum += (final["draw"] - (1 if actual == "D" else 0)) ** 2
        brier_sum += (final["away_win"] - (1 if actual == "A" else 0)) ** 2

    acc = correct / n_test
    brier = brier_sum / (n_test * 3)
    print(f"\nStacking Test: acc={acc:.3f}, brier={brier:.4f}")

    # Save
    ensemble_path = model_dir / f'stacking_{league_code}.json'
    ensemble.save(ensemble_path)
    print(f"Ensemble saved to {ensemble_path}")

    return ensemble, {"accuracy": round(acc, 4), "brier": round(brier, 4)}
