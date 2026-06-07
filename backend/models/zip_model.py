# -*- coding: utf-8 -*-
"""
P1-1: Zero-Inflated Poisson Model (ZIP)
========================================
Standard Poisson underestimates 0-0 draws in football.
ZIP adds an extra "excess zero" probability:
  P(X=0) = pi + (1-pi) * exp(-lambda)
  P(X=k) = (1-pi) * Poisson(k, lambda)  for k > 0

Reference: App Sci 2024 "Predicting Football Match Results Using Poisson Regression"
"""
import math
import numpy as np
from scipy.stats import poisson


class ZeroInflatedPoisson:
    """
    Zero-Inflated Poisson model for football goals.
    
    Parameters:
        lambda_home: expected home goals (from DC model)
        lambda_away: expected away goals (from DC model)
        pi_home: excess zero probability for home team
        pi_away: excess zero probability for away team
    """

    def __init__(self):
        self.pi_home = 0.0  # excess zero rate for home goals
        self.pi_away = 0.0  # excess zero rate for away goals
        self.fitted = False

    def fit(self, home_goals, away_goals):
        """
        Fit ZIP parameters from observed goal data.
        Estimates pi (excess zero probability) via MLE.
        """
        hg = np.array(home_goals, dtype=float)
        ag = np.array(away_goals, dtype=float)
        
        avg_hg = np.mean(hg)
        avg_ag = np.mean(ag)
        
        # Estimate pi: proportion of excess zeros
        # P(X=0) = pi + (1-pi)*exp(-lambda)
        # => pi = (P(X=0) - exp(-lambda)) / (1 - exp(-lambda))
        
        n = len(hg)
        zero_rate_h = np.sum(hg == 0) / n
        zero_rate_a = np.sum(ag == 0) / n
        
        exp_neg_lam_h = np.exp(-avg_hg)
        exp_neg_lam_a = np.exp(-avg_ag)
        
        # Clip to valid range
        self.pi_home = max(0, min((zero_rate_h - exp_neg_lam_h) / max(1 - exp_neg_lam_h, 1e-10), 0.5))
        self.pi_away = max(0, min((zero_rate_a - exp_neg_lam_a) / max(1 - exp_neg_lam_a, 1e-10), 0.5))
        self.fitted = True
        
        print("ZIP fitted: pi_home=" + str(round(self.pi_home, 4)) + " pi_away=" + str(round(self.pi_away, 4)))
        return True

    def pmf(self, k, lam, pi):
        """ZIP probability mass function."""
        if k == 0:
            return pi + (1 - pi) * math.exp(-lam)
        else:
            return (1 - pi) * poisson.pmf(k, lam)

    def predict_match(self, lam_home, lam_away, max_goals=10):
        """
        Predict match outcome using ZIP model.
        
        Args:
            lam_home: expected home goals (from DC/Poisson model)
            lam_away: expected away goals
            
        Returns:
            dict with home_win, draw, away_win, score_distribution
        """
        pi_h = self.pi_home if self.fitted else 0.0
        pi_a = self.pi_away if self.fitted else 0.0
        
        n = max_goals + 1
        prob_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                p_h = self.pmf(i, lam_home, pi_h)
                p_a = self.pmf(j, lam_away, pi_a)
                prob_matrix[i, j] = p_h * p_a
        
        # Normalize
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total
        
        home_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i > j]))
        draw = float(np.sum([prob_matrix[i, i] for i in range(n)]))
        away_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i < j]))
        
        # Score distribution
        scores = {}
        for i in range(min(5, n)):
            for j in range(min(5, n)):
                scores[str(i) + "-" + str(j)] = round(float(prob_matrix[i, j]), 4)
        
        return {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "expected_goals": {"home": round(float(lam_home), 2), "away": round(float(lam_away), 2)},
            "score_distribution": scores,
            "model": "zip",
            "pi": {"home": round(pi_h, 4), "away": round(pi_a, 4)},
        }
