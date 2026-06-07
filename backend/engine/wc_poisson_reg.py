# -*- coding: utf-8 -*-
"""
Poisson Regression for international football prediction.

Following Groll et al. (2015):
"Prediction of major international soccer tournaments based on
 team-specific regularized Poisson regression"

Uses 23 features to predict expected goals (lambda_home, lambda_away).
"""
import json
import os
import sys
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_features import compute_match_features, FEATURE_NAMES
from engine.wc_dc_international import normalize_team, MODEL_DIR


class PoissonRegression:
    """Poisson regression for match prediction."""
    
    def __init__(self):
        self.n_features = len(FEATURE_NAMES)
        # Separate coefficients for home and away goals
        self.beta_home = np.zeros(self.n_features)
        self.beta_away = np.zeros(self.n_features)
        self.intercept_home = 0.0
        self.intercept_away = 0.0
        self.fitted = False
    
    def _predict_lambda(self, X, beta, intercept):
        """Predict expected goals: lambda = exp(intercept + X @ beta)."""
        return np.exp(intercept + X @ beta)
    
    def _log_likelihood(self, params, X, y_home, y_away, alpha=0.01):
        """Negative log-likelihood with L2 regularization."""
        n = self.n_features
        
        beta_h = params[:n]
        beta_a = params[n:2*n]
        int_h = params[-2]
        int_a = params[-1]
        
        lam_h = self._predict_lambda(X, beta_h, int_h)
        lam_a = self._predict_lambda(X, beta_a, int_a)
        
        # Poisson log-likelihood
        ll_h = np.sum(y_home * np.log(lam_h + 1e-10) - lam_h)
        ll_a = np.sum(y_away * np.log(lam_a + 1e-10) - lam_a)
        
        # L2 regularization
        reg = alpha * (np.sum(beta_h**2) + np.sum(beta_a**2))
        
        return -(ll_h + ll_a - reg)
    
    def fit(self, X, y_home, y_away, alpha=0.01, max_iter=2000):
        """Train the model."""
        print(f"Training Poisson Regression: {X.shape[0]} samples, {X.shape[1]} features")
        
        # Normalize features
        self.mean = np.mean(X, axis=0)
        self.std = np.std(X, axis=0) + 1e-8
        X_norm = (X - self.mean) / self.std
        
        n = self.n_features
        x0 = np.zeros(2 * n + 2)
        x0[-2] = np.log(np.mean(y_home) + 1e-10)  # Intercept init
        x0[-1] = np.log(np.mean(y_away) + 1e-10)
        
        result = minimize(
            self._log_likelihood, x0,
            args=(X_norm, y_home, y_away, alpha),
            method='L-BFGS-B',
            options={'maxiter': max_iter, 'ftol': 1e-7}
        )
        
        self.beta_home = result.x[:n]
        self.beta_away = result.x[n:2*n]
        self.intercept_home = result.x[-2]
        self.intercept_away = result.x[-1]
        self.fitted = True
        
        ll = -result.fun
        print(f"Done: LL={ll:.2f}, iters={result.nit}")
        
        # Print top features
        self._print_top_features()
        
        return True
    
    def _print_top_features(self):
        """Print most important features."""
        # Feature importance = absolute coefficient value
        importance_h = np.abs(self.beta_home)
        importance_a = np.abs(self.beta_away)
        importance = (importance_h + importance_a) / 2
        
        sorted_idx = np.argsort(importance)[::-1]
        
        print("\nTop 10 features:")
        for i in range(min(10, len(sorted_idx))):
            idx = sorted_idx[i]
            print(f"  {FEATURE_NAMES[idx]:30s}  "
                  f"home={self.beta_home[idx]:+.4f}  away={self.beta_away[idx]:+.4f}")
    
    def predict(self, features):
        """Predict WDL from feature dict."""
        if not self.fitted:
            raise RuntimeError("Model not fitted")
        
        x = np.array([features.get(f, 0) for f in FEATURE_NAMES])
        x_norm = (x - self.mean) / self.std
        
        lam_h = float(np.exp(self.intercept_home + x_norm @ self.beta_home))
        lam_a = float(np.exp(self.intercept_away + x_norm @ self.beta_away))
        
        # Compute WDL from lambda (simple Poisson)
        from scipy.stats import poisson
        n = 9
        prob = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                prob[i, j] = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
        
        total = prob.sum()
        if total > 0:
            prob /= total
        
        home_win = float(sum(prob[i, j] for i in range(n) for j in range(n) if i > j))
        draw = float(sum(prob[i, i] for i in range(n)))
        away_win = float(sum(prob[i, j] for i in range(n) for j in range(n) if i < j))
        
        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4),
            'expected_goals': {'home': round(lam_h, 2), 'away': round(lam_a, 2)},
        }
    
    def save(self, filepath=None):
        if filepath is None:
            filepath = MODEL_DIR / 'poisson_intl_latest.json'
        with open(filepath, 'w') as f:
            json.dump({
                'model_type': 'poisson_regression',
                'n_features': self.n_features,
                'beta_home': self.beta_home.tolist(),
                'beta_away': self.beta_away.tolist(),
                'intercept_home': float(self.intercept_home),
                'intercept_away': float(self.intercept_away),
                'mean': self.mean.tolist(),
                'std': self.std.tolist(),
            }, f, indent=2)
        print(f"Saved to {filepath}")
    
    def load(self, filepath):
        with open(filepath) as f:
            data = json.load(f)
        self.beta_home = np.array(data['beta_home'])
        self.beta_away = np.array(data['beta_away'])
        self.intercept_home = data['intercept_home']
        self.intercept_away = data['intercept_away']
        self.mean = np.array(data['mean'])
        self.std = np.array(data['std'])
        self.n_features = data['n_features']
        self.fitted = True


def prepare_dataset(start_date='2014-01-01'):
    """Prepare training dataset with features."""
    print("Loading matches ...")
    rows = query(
        "SELECT home_club_name as home, away_club_name as away, "
        "home_club_goals as home_goals, away_club_goals as away_goals, "
        "competition_id, date "
        "FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND home_club_goals IS NOT NULL AND date >= %s ORDER BY date",
        [start_date], db='football_pred'
    )
    
    # Get FIFA teams
    fifa_rows = query(
        "SELECT DISTINCT team FROM ("
        "SELECT home_club_name as team FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND date >= %s "
        "UNION "
        "SELECT away_club_name as team FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','UNL','CNL','AFQL','ACQL','GC') "
        "AND date >= %s "
        ") t",
        [start_date, start_date], db='football_pred'
    )
    fifa_teams = {normalize_team(r['team']) for r in fifa_rows}
    
    print(f"Computing features for {len(rows)} matches ...")
    X = []
    y_home = []
    y_away = []
    valid = 0
    skipped = 0
    
    for i, r in enumerate(rows):
        home = normalize_team(r['home'])
        away = normalize_team(r['away'])
        
        if home not in fifa_teams or away not in fifa_teams:
            skipped += 1
            continue
        
        try:
            features = compute_match_features(home, away)
            x = [features.get(f, 0) for f in FEATURE_NAMES]
            X.append(x)
            y_home.append(int(r['home_goals']))
            y_away.append(int(r['away_goals']))
            valid += 1
        except Exception as e:
            skipped += 1
            continue
        
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(rows)} ({valid} valid)")
    
    X = np.array(X)
    y_home = np.array(y_home)
    y_away = np.array(y_away)
    
    print(f"Dataset: {valid} valid, {skipped} skipped, {X.shape[1]} features")
    return X, y_home, y_away


def train_and_save():
    """Train Poisson regression and save."""
    print("=" * 60)
    print("Training Poisson Regression (International)")
    print("=" * 60)
    
    X, y_home, y_away = prepare_dataset()
    model = PoissonRegression()
    model.fit(X, y_home, y_away, alpha=0.01)
    model.save()
    
    return model


if __name__ == '__main__':
    model = train_and_save()
    
    print("\n=== Predictions ===")
    tests = [
        ('Brazil', 'Croatia'), ('France', 'Morocco'),
        ('Argentina', 'Saudi Arabia'), ('England', 'Iran'),
        ('Germany', 'Japan'), ('Spain', 'Italy'),
    ]
    for home, away in tests:
        features = compute_match_features(home, away)
        pred = model.predict(features)
        print(f"  {home:20s} vs {away:20s}  "
              f"WDL: {pred['home_win']:.1%}/{pred['draw']:.1%}/{pred['away_win']:.1%}  "
              f"xG: {pred['expected_goals']['home']:.2f}-{pred['expected_goals']['away']:.2f}")
