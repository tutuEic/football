# -*- coding: utf-8 -*-
"""
Stacking Ensemble for WC Prediction.

Trains a Logistic Regression meta-learner on base model predictions.
Uses temporal split: train on 2014-2023, test on 2024-2026.

Based on Schauberger & Groll (2018):
"Predicting matches in international football tournaments with random forests"
"""
import json
import os
import sys
import math
import numpy as np
from datetime import datetime, date
from pathlib import Path
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_dc_international import InternationalDixonColes, normalize_team, MODEL_DIR
from engine.wc_poisson_reg import PoissonRegression
from engine.wc_elo_poisson import predict_elo_poisson
from engine.wc_features import compute_match_features, FEATURE_NAMES
from engine.wc_elo_adapter import analyze_squad_elo


class StackingEnsemble:
    """Logistic Regression meta-learner for combining base models."""
    
    def __init__(self, n_features=13):
        # Weights for [home_win, draw, away_win] prediction
        # Features: [bias, dc_h, dc_d, dc_a, pr_h, pr_d, pr_a, ep_h, ep_d, ep_a, elo_diff, cohesion_h, cohesion_a]
        self.n_features = n_features
        self.beta_hw = np.zeros(n_features)  # home_win coefficients
        self.beta_dr = np.zeros(n_features)  # draw coefficients
        self.beta_aw = np.zeros(n_features)  # away_win coefficients
        self.fitted = False
    
    def _softmax(self, x):
        """Softmax for 3-class output."""
        e = np.exp(x - np.max(x))
        return e / e.sum()
    
    def _predict_proba(self, features):
        """Predict WDL probabilities from stacking features."""
        hw = 1.0 / (1.0 + np.exp(-features @ self.beta_hw))
        dr = 1.0 / (1.0 + np.exp(-features @ self.beta_dr))
        aw = 1.0 / (1.0 + np.exp(-features @ self.beta_aw))
        
        # Normalize to sum to 1
        total = hw + dr + aw
        if total > 0:
            return np.array([hw/total, dr/total, aw/total])
        return np.array([0.33, 0.33, 0.34])
    
    def _log_loss(self, params, X, y):
        """Negative log-likelihood for 3-class classification."""
        n = self.n_features
        self.beta_hw = params[:n]
        self.beta_dr = params[n:2*n]
        self.beta_aw = params[2*n:3*n]
        
        ll = 0.0
        for i in range(len(X)):
            probs = self._predict_proba(X[i])
            # y is 0 (home win), 1 (draw), 2 (away win)
            ll += np.log(max(probs[int(y[i])], 1e-10))
        
        # L2 regularization
        reg = 0.01 * (np.sum(self.beta_hw**2) + np.sum(self.beta_dr**2) + np.sum(self.beta_aw**2))
        return -(ll - reg)
    
    def fit(self, X, y, max_iter=1000):
        """Train the stacking model."""
        print(f"Training Stacking: {X.shape[0]} samples, {X.shape[1]} features")
        
        x0 = np.zeros(3 * self.n_features)
        # Initialize biases
        x0[0] = 0.0   # home_win bias
        x0[self.n_features] = -0.5  # draw bias (lower prior)
        x0[2 * self.n_features] = 0.0  # away_win bias
        
        result = minimize(
            self._log_loss, x0,
            args=(X, y),
            method='L-BFGS-B',
            options={'maxiter': max_iter, 'ftol': 1e-7}
        )
        
        n = self.n_features
        self.beta_hw = result.x[:n]
        self.beta_dr = result.x[n:2*n]
        self.beta_aw = result.x[2*n:3*n]
        self.fitted = True
        
        ll = -result.fun
        print(f"Done: LL={ll:.2f}, iters={result.nit}")
        
        # Print learned weights
        self._print_weights()
        
        return True
    
    def _print_weights(self):
        """Print learned stacking weights."""
        labels = ['bias', 'dc_H', 'dc_D', 'dc_A', 'pr_H', 'pr_D', 'pr_A', 
                  'ep_H', 'ep_D', 'ep_A', 'elo_diff', 'coh_H', 'coh_A']
        print("\nStacking weights:")
        print(f"  {'':10s} {'HomeWin':>8s} {'Draw':>8s} {'AwayWin':>8s}")
        for i, label in enumerate(labels[:self.n_features]):
            print(f"  {label:10s} {self.beta_hw[i]:>+8.3f} {self.beta_dr[i]:>+8.3f} {self.beta_aw[i]:>+8.3f}")
    
    def predict(self, dc_wdl, pr_wdl, ep_wdl, elo_diff=0.0, cohesion_h=0.5, cohesion_a=0.5):
        """Predict using stacking."""
        if not self.fitted:
            raise RuntimeError("Stacking not fitted")
        
        features = np.array([1.0] + dc_wdl + pr_wdl + ep_wdl + [elo_diff, cohesion_h, cohesion_a])
        probs = self._predict_proba(features)
        
        return {
            'home_win': round(float(probs[0]), 4),
            'draw': round(float(probs[1]), 4),
            'away_win': round(float(probs[2]), 4),
        }
    
    def save(self, filepath=None):
        if filepath is None:
            filepath = MODEL_DIR / 'stacking_intl_latest.json'
        with open(filepath, 'w') as f:
            json.dump({
                'model_type': 'stacking_ensemble',
                'n_features': self.n_features,
                'beta_hw': self.beta_hw.tolist(),
                'beta_dr': self.beta_dr.tolist(),
                'beta_aw': self.beta_aw.tolist(),
            }, f, indent=2)
        print(f"Saved to {filepath}")
    
    def load(self, filepath):
        with open(filepath) as f:
            data = json.load(f)
        self.n_features = data.get('n_features', 10)
        self.beta_hw = np.array(data['beta_hw'])
        self.beta_dr = np.array(data['beta_dr'])
        self.beta_aw = np.array(data['beta_aw'])
        self.fitted = True


def prepare_stacking_dataset(split_date='2024-01-01'):
    """Prepare dataset for stacking training."""
    print("Loading matches ...")
    rows = query(
        "SELECT home_club_name as home, away_club_name as away, "
        "home_club_goals as home_goals, away_club_goals as away_goals, "
        "competition_id, date "
        "FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND home_club_goals IS NOT NULL AND date >= '2014-01-01' ORDER BY date",
        db='football_pred'
    )
    
    # Get FIFA teams
    fifa_rows = query(
        "SELECT DISTINCT team FROM ("
        "SELECT home_club_name as team FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND date >= '2014-01-01' "
        "UNION "
        "SELECT away_club_name as team FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND date >= '2014-01-01' "
        ") t",
        db='football_pred'
    )
    fifa_teams = {normalize_team(r['team']) for r in fifa_rows}
    
    # Load base models
    print("Loading base models ...")
    dc_model = InternationalDixonColes()
    dc_path = MODEL_DIR / 'bayes_dc_intl_latest.json'
    if dc_path.exists():
        dc_model.load(dc_path)
    else:
        dc_path2 = MODEL_DIR / 'dc_intl_latest.json'
        dc_model.load(dc_path2)
    
    pr_model = PoissonRegression()
    pr_path = MODEL_DIR / 'poisson_intl_latest.json'
    pr_model.load(pr_path)
    
    # Build dataset
    print(f"Building stacking dataset ({len(rows)} matches) ...")
    X = []
    y = []
    train_count = 0
    test_count = 0
    
    team_cache = {}  # Cache team analyses to avoid recomputation
    for i, r in enumerate(rows):
        home = normalize_team(r['home'])
        away = normalize_team(r['away'])
        
        if home not in fifa_teams or away not in fifa_teams:
            continue
        
        match_date = str(r['date'])
        
        # Determine actual result
        hg = int(r['home_goals'])
        ag = int(r['away_goals'])
        if hg > ag:
            result = 0  # home win
        elif hg == ag:
            result = 1  # draw
        else:
            result = 2  # away win
        
        # Get base model predictions
        try:
            dc_pred = dc_model.get_match_probs(home, away)
            dc_wdl = [dc_pred['home_win'], dc_pred['draw'], dc_pred['away_win']]
        except:
            dc_wdl = [0.45, 0.25, 0.30]
        
        try:
            features = compute_match_features(home, away)
            pr_pred = pr_model.predict(features)
            pr_wdl = [pr_pred['home_win'], pr_pred['draw'], pr_pred['away_win']]
        except:
            pr_wdl = [0.45, 0.25, 0.30]
        
        try:
            ep_pred = predict_elo_poisson(home, away)
            ep_wdl = [ep_pred['home_win'], ep_pred['draw'], ep_pred['away_win']]
        except:
            ep_wdl = [0.45, 0.25, 0.30]
        
        # Features: [bias, dc_h, dc_d, dc_a, pr_h, pr_d, pr_a, ep_h, ep_d, ep_a, elo_diff, cohesion_h, cohesion_a]
        # Use pre-computed team analysis cache
        if home not in team_cache:
            try:
                team_cache[home] = analyze_squad_elo(home)
            except:
                team_cache[home] = {'elo_bonus': 0, 'cohesion': 0.5}
        if away not in team_cache:
            try:
                team_cache[away] = analyze_squad_elo(away)
            except:
                team_cache[away] = {'elo_bonus': 0, 'cohesion': 0.5}
        
        analysis_h = team_cache[home]
        analysis_a = team_cache[away]
        elo_diff = (analysis_h.get('elo_bonus', 0) - analysis_a.get('elo_bonus', 0)) / 100.0
        cohesion_h = analysis_h.get('cohesion', 0.5)
        cohesion_a = analysis_a.get('cohesion', 0.5)
        
        x = [1.0] + dc_wdl + pr_wdl + ep_wdl + [elo_diff, cohesion_h, cohesion_a]
        X.append(x)
        y.append(result)
        
        if match_date < split_date:
            train_count += 1
        else:
            test_count += 1
        
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(rows)} processed")
    
    X = np.array(X)
    y = np.array(y)
    
    # Temporal split
    dates = [str(r['date']) for r in rows if normalize_team(r['home']) in fifa_teams]
    # Use index-based split since dates might not align perfectly
    split_idx = train_count
    
    X_train = X[:split_idx]
    y_train = y[:split_idx]
    X_test = X[split_idx:]
    y_test = y[split_idx:]
    
    print(f"Dataset: train={len(X_train)}, test={len(X_test)}")
    return X_train, y_train, X_test, y_test


def evaluate_stacking(model, X_test, y_test):
    """Evaluate stacking model on test set."""
    correct = 0
    total = len(X_test)
    
    for i in range(total):
        features = X_test[i]
        probs = model._predict_proba(features)
        pred = np.argmax(probs)
        if pred == int(y_test[i]):
            correct += 1
    
    accuracy = correct / total if total > 0 else 0
    print(f"Test accuracy: {accuracy:.1%} ({correct}/{total})")
    return accuracy


def train_and_save():
    """Train stacking model and save."""
    print("=" * 60)
    print("Training Stacking Ensemble")
    print("=" * 60)
    
    X_train, y_train, X_test, y_test = prepare_stacking_dataset()
    
    model = StackingEnsemble()
    model.fit(X_train, y_train)
    
    if len(X_test) > 0:
        evaluate_stacking(model, X_test, y_test)
    
    model.save()
    return model


if __name__ == '__main__':
    model = train_and_save()




