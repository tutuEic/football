# -*- coding: utf-8 -*-
"""
Poisson Regression model for football prediction.
Uses features to predict expected goals (lambda, mu) via log-linear model.
"""
import sys, os
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
from features.feature_store import FEATURE_NAMES


class PoissonRegression:
    """Feature-enhanced Poisson regression for match prediction."""

    def __init__(self):
        self.beta_home = None  # Coefficients for home goals
        self.beta_away = None  # Coefficients for away goals
        self.feature_names = FEATURE_NAMES
        self.n_features = len(FEATURE_NAMES)
        self.fitted = False
        self.intercept_home = 0.0
        self.intercept_away = 0.0

    def _predict_lambda(self, features: np.ndarray) -> np.ndarray:
        """Predict expected home goals for each sample."""
        log_lam = self.intercept_home + features @ self.beta_home
        return np.exp(np.clip(log_lam, -5, 3))  # Clamp to [0.007, 20]

    def _predict_mu(self, features: np.ndarray) -> np.ndarray:
        """Predict expected away goals for each sample."""
        log_mu = self.intercept_away + features @ self.beta_away
        return np.exp(np.clip(log_mu, -5, 3))

    def _neg_log_likelihood(self, params, X, home_goals, away_goals):
        """Negative log-likelihood for Poisson regression."""
        n_feat = self.n_features

        self.intercept_home = params[0]
        self.beta_home = params[1:1 + n_feat]
        self.intercept_away = params[1 + n_feat]
        self.beta_away = params[1 + n_feat + 1:]

        lam = self._predict_lambda(X)
        mu = self._predict_mu(X)

        # Poisson log-likelihood
        ll_home = poisson.logpmf(home_goals.astype(int), np.maximum(lam, 1e-10))
        ll_away = poisson.logpmf(away_goals.astype(int), np.maximum(mu, 1e-10))

        # L2 regularization
        reg = 0.01 * (np.sum(self.beta_home ** 2) + np.sum(self.beta_away ** 2))

        return -(np.sum(ll_home) + np.sum(ll_away)) + reg

    def fit(self, X: np.ndarray, home_goals: np.ndarray, away_goals: np.ndarray,
            max_iter: int = 1000):
        """
        Train the Poisson regression model.

        Args:
            X: Feature matrix (n_samples, n_features)
            home_goals: Array of home goals
            away_goals: Array of away goals
        """
        n_feat = X.shape[1]
        self.n_features = n_feat

        # Initialize parameters
        x0 = np.zeros(2 + 2 * n_feat)
        x0[0] = np.log(np.mean(home_goals) + 0.01)  # intercept_home
        x0[1 + n_feat] = np.log(np.mean(away_goals) + 0.01)  # intercept_away

        # Standardize features
        self.feature_mean = np.mean(X, axis=0)
        self.feature_std = np.std(X, axis=0) + 1e-8
        X_scaled = (X - self.feature_mean) / self.feature_std

        result = minimize(
            self._neg_log_likelihood, x0,
            args=(X_scaled, home_goals, away_goals),
            method='L-BFGS-B',
            options={'maxiter': max_iter, 'disp': False}
        )

        if result.success:
            self.fitted = True
            print(f"Poisson regression converged: LL={-result.fun:.2f}")
        else:
            print(f"Warning: Poisson regression did not converge: {result.message}")
            self.fitted = True  # Use anyway

        return self.fitted

    def predict(self, features: dict) -> dict:
        """Predict match outcome given feature dict."""
        if not self.fitted:
            raise ValueError("Model not fitted")

        # Build feature vector
        x = np.array([features.get(f, 0) for f in self.feature_names])
        x_scaled = (x - self.feature_mean) / self.feature_std

        lam = float(self._predict_lambda(x_scaled.reshape(1, -1))[0])
        mu = float(self._predict_mu(x_scaled.reshape(1, -1))[0])

        # Calculate W/D/L probabilities (Poisson grid)
        max_goals = 8
        n = max_goals + 1
        prob_h = np.array([poisson.pmf(i, lam) for i in range(n)])
        prob_a = np.array([poisson.pmf(j, mu) for j in range(n)])

        home_win = sum(prob_h[i] * prob_a[j] for i in range(n) for j in range(n) if i > j)
        draw = sum(prob_h[i] * prob_a[i] for i in range(n))
        away_win = sum(prob_h[i] * prob_a[j] for i in range(n) for j in range(n) if i < j)

        total = home_win + draw + away_win
        home_win /= total
        draw /= total
        away_win /= total

        return {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "expected_goals": {"home": round(lam, 2), "away": round(mu, 2)},
            "model": "poisson_regression",
        }

    def save(self, path):
        data = {
            "intercept_home": self.intercept_home,
            "intercept_away": self.intercept_away,
            "beta_home": self.beta_home.tolist(),
            "beta_away": self.beta_away.tolist(),
            "feature_mean": self.feature_mean.tolist(),
            "feature_std": self.feature_std.tolist(),
            "feature_names": self.feature_names,
            "n_features": self.n_features,
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding='utf-8')

    def load(self, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        self.intercept_home = data["intercept_home"]
        self.intercept_away = data["intercept_away"]
        self.beta_home = np.array(data["beta_home"])
        self.beta_away = np.array(data["beta_away"])
        self.feature_mean = np.array(data["feature_mean"])
        self.feature_std = np.array(data["feature_std"])
        self.feature_names = data["feature_names"]
        self.n_features = data["n_features"]
        self.fitted = True
