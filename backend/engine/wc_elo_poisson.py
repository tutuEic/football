# -*- coding: utf-8 -*-
"""
Elo-Poisson Model for international football.

No training required - directly derives expected goals from player Elo ratings.
Based on the principle that team strength = sum of player strengths.

Useful as a cold-start model for teams with few matches.
"""
import sys
import os
import math
import numpy as np
from scipy.stats import poisson

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.wc_elo_adapter import analyze_squad_elo


class EloPoissonModel:
    """
    Derives match predictions directly from player Elo ratings.
    
    Formula:
        lambda_home = exp(alpha_home + beta_away + gamma)
        lambda_away = exp(alpha_away + beta_home)
    
    where alpha/beta are derived from team Elo ratings.
    """
    
    def __init__(self):
        # Calibration parameters (tuned to match international goal averages)
        self.base_lambda = 1.35  # Average goals per team in internationals
        self.elo_scale = 400.0   # Elo scale factor
        self.gamma = 0.15        # Home advantage (in log-space)
    
    def _team_strength(self, analysis):
        """Convert Elo analysis to attack/defence strength."""
        # attack_quality (0-99) -> attack strength
        # defense_quality (0-99) -> defence strength (lower = better defence)
        att_q = analysis['attack_quality']
        def_q = analysis['defense_quality']
        
        # Normalize: 70 = average, scale to [-1, +1] range
        alpha = (att_q - 70) / 30.0
        beta = -(def_q - 70) / 30.0  # Negative: better defence = lower beta
        
        return alpha, beta
    
    def predict(self, home_team, away_team):
        """Predict match outcome."""
        try:
            analysis_h = analyze_squad_elo(home_team)
            analysis_a = analyze_squad_elo(away_team)
        except Exception:
            return self._default_probs()
        
        alpha_h, beta_h = self._team_strength(analysis_h)
        alpha_a, beta_a = self._team_strength(analysis_a)
        
        # Expected goals
        lam_h = self.base_lambda * math.exp(alpha_h + beta_a + self.gamma)
        lam_a = self.base_lambda * math.exp(alpha_a + beta_h)
        
        # Clamp to reasonable range
        lam_h = max(0.3, min(lam_h, 4.0))
        lam_a = max(0.2, min(lam_a, 3.5))
        
        # Compute WDL
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
        
        best = np.unravel_index(prob.argmax(), prob.shape)
        over_25 = float(sum(prob[i, j] for i in range(n) for j in range(n) if i + j > 2))
        
        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4),
            'expected_goals': {'home': round(float(lam_h), 2), 'away': round(float(lam_a), 2)},
            'most_likely_score': f"{best[0]}-{best[1]}",
            'over_25': round(over_25, 4),
        }
    
    def _default_probs(self):
        return {
            'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30,
            'expected_goals': {'home': 1.3, 'away': 1.1},
            'most_likely_score': '1-0', 'over_25': 0.55,
        }


# Singleton
_model = EloPoissonModel()


def predict_elo_poisson(home_team, away_team):
    """Module-level prediction function."""
    return _model.predict(home_team, away_team)


if __name__ == '__main__':
    print("=== Elo-Poisson Predictions ===\n")
    tests = [
        ('Brazil', 'Croatia'), ('France', 'Morocco'),
        ('Argentina', 'Saudi Arabia'), ('England', 'Iran'),
        ('Germany', 'Japan'), ('Spain', 'Italy'),
        ('France', 'Brazil'), ('Argentina', 'France'),
    ]
    for home, away in tests:
        pred = _model.predict(home, away)
        print(f"  {home:20s} vs {away:20s}  "
              f"WDL: {pred['home_win']:.1%}/{pred['draw']:.1%}/{pred['away_win']:.1%}  "
              f"xG: {pred['expected_goals']['home']:.2f}-{pred['expected_goals']['away']:.2f}")
