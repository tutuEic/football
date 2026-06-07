# -*- coding: utf-8 -*-
"""
P1-2: Skellam Distribution Model
==================================
Models goal difference directly rather than home/away goals separately.

If X ~ Poisson(lambda) and Y ~ Poisson(mu), then Z = X - Y ~ Skellam(lambda, mu).

PMF: P(Z=k) = exp(-(lam+mu)) * (lam/mu)^(k/2) * I_|k|(2*sqrt(lam*mu))

where I_k is the modified Bessel function of the first kind.

Advantages over separate Poisson:
1. Directly models goal difference (what matters for W/D/L)
2. Naturally handles correlation between home/away goals
3. More efficient for predicting match outcomes

Reference: BJB 2025 "Probabilistic model based on the Skellam distribution"
"""
import math
import numpy as np
from scipy.stats import poisson
from scipy.special import iv


class SkellamModel:
    """
    Skellam distribution model for football goal difference.
    """

    def __init__(self):
        self.fitted = True  # No training needed, just needs lambda/mu

    def pmf(self, k, lam, mu):
        """
        Skellam PMF: P(goal_diff = k).
        k can be negative (away wins), 0 (draw), positive (home wins).
        """
        if lam <= 0 or mu <= 0:
            return 0.0
        
        # P(Z=k) = exp(-(lam+mu)) * (lam/mu)^(k/2) * I_|k|(2*sqrt(lam*mu))
        nu = 2 * math.sqrt(lam * mu)
        log_p = -(lam + mu) + (k / 2.0) * math.log(lam / mu) if lam > 0 and mu > 0 else -(lam + mu)
        
        # Use log for numerical stability
        try:
            bessel_val = iv(abs(k), nu)
            if bessel_val <= 0:
                return 0.0
            result = math.exp(-(lam + mu)) * (lam / mu) ** (k / 2.0) * bessel_val
            return max(result, 0.0)
        except (OverflowError, ValueError):
            return 0.0

    def predict_match(self, lam_home, lam_away, max_diff=10):
        """
        Predict match outcome using Skellam distribution.
        
        Args:
            lam_home: expected home goals
            lam_away: expected away goals
            
        Returns:
            dict with home_win, draw, away_win, goal_diff_distribution
        """
        # Compute P(goal_diff = k) for k in [-max_diff, max_diff]
        diff_probs = {}
        for k in range(-max_diff, max_diff + 1):
            diff_probs[k] = self.pmf(k, lam_home, lam_away)
        
        # Normalize
        total = sum(diff_probs.values())
        if total > 0:
            diff_probs = {k: v / total for k, v in diff_probs.items()}
        
        # W/D/L
        home_win = sum(v for k, v in diff_probs.items() if k > 0)
        draw = diff_probs.get(0, 0)
        away_win = sum(v for k, v in diff_probs.items() if k < 0)
        
        # Goal difference distribution (top outcomes)
        gd_dist = {}
        for k in range(-5, 6):
            p = diff_probs.get(k, 0)
            if p > 0.001:
                gd_dist[k] = round(p, 4)
        
        # Most likely goal difference
        best_diff = max(diff_probs.items(), key=lambda x: x[1])
        
        # Score distribution approximation
        # From goal difference + expected goals, estimate score probabilities
        score_dist = self._approximate_scores(lam_home, lam_away, max_goals=6)
        
        return {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "expected_goals": {"home": round(float(lam_home), 2), "away": round(float(lam_away), 2)},
            "goal_diff_distribution": {str(k): v for k, v in gd_dist.items()},
            "most_likely_diff": int(best_diff[0]),
            "most_likely_diff_prob": round(best_diff[1], 4),
            "score_distribution": score_dist,
            "model": "skellam",
        }

    def _approximate_scores(self, lam_h, lam_a, max_goals=6):
        """
        Approximate score distribution using independent Poisson (for display).
        The Skellam model gives better W/D/L but doesn't directly give scores.
        """
        scores = {}
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
                if p > 0.001:
                    scores[str(i) + "-" + str(j)] = round(p, 4)
        return scores

    def predict_with_dc_correction(self, lam_home, lam_away, rho, max_goals=10):
        """
        Predict using Skellam for W/D/L but apply DC tau correction.
        This combines Skellam's direct goal-difference modeling with DC's low-score correlation.
        """
        n = max_goals + 1
        
        # First, compute DC-corrected joint distribution
        prob_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam_home) * poisson.pmf(j, lam_away)
                # DC tau correction
                if i == 0 and j == 0:
                    tau = max(1 - lam_home * lam_away * rho, 1e-10)
                elif i == 0 and j == 1:
                    tau = 1 + lam_home * rho
                elif i == 1 and j == 0:
                    tau = 1 + lam_away * rho
                elif i == 1 and j == 1:
                    tau = max(1 - rho, 1e-10)
                else:
                    tau = 1.0
                prob_matrix[i, j] = max(tau * p, 0)
        
        # Normalize
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total
        
        # Compute W/D/L from joint distribution
        home_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i > j]))
        draw = float(np.sum([prob_matrix[i, i] for i in range(n)]))
        away_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i < j]))
        
        # Goal difference distribution from DC-corrected matrix
        gd_probs = {}
        for i in range(n):
            for j in range(n):
                diff = i - j
                gd_probs[diff] = gd_probs.get(diff, 0) + prob_matrix[i, j]
        
        gd_dist = {}
        for k in range(-5, 6):
            p = gd_probs.get(k, 0)
            if p > 0.001:
                gd_dist[k] = round(p, 4)
        
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
            "goal_diff_distribution": {str(k): v for k, v in gd_dist.items()},
            "score_distribution": scores,
            "model": "skellam_dc",
        }
