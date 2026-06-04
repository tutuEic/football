# -*- coding: utf-8 -*-
"""
Monte Carlo match simulator with Dixon-Coles tau correction
and match context adjustments for realistic big-match behavior.
"""
import numpy as np
from collections import Counter
import time
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from strength import calc_team_strength, squad_summary
from dixon_coles import DixonColes
from scipy.stats import poisson

# Match context goal adjustment factors
# Based on football analytics research:
# - Big matches (cup KO, CL knockout) tend to be more cautious -> fewer goals
# - Derbies tend to be more intense -> slightly more goals
# - Relegation battles -> desperate attacking -> slightly more goals
CONTEXT_FACTORS = {
    "league":          {"goal_mult": 1.00, "draw_shift": 0.00, "label": "League match"},
    "derby":           {"goal_mult": 1.08, "draw_shift": -0.02, "label": "Derby / Rivalry"},
    "title_decider":   {"goal_mult": 0.92, "draw_shift": 0.03, "label": "Title decider"},
    "relegation":      {"goal_mult": 1.05, "draw_shift": -0.01, "label": "Relegation battle"},
    "cup_ko":          {"goal_mult": 0.88, "draw_shift": 0.04, "label": "Cup knockout"},
    "cup_final":       {"goal_mult": 0.82, "draw_shift": 0.06, "label": "Cup final"},
    "cl_knockout":     {"goal_mult": 0.85, "draw_shift": 0.05, "label": "CL knockout"},
    "cl_final":        {"goal_mult": 0.80, "draw_shift": 0.07, "label": "Champions League final"},
    "friendly":        {"goal_mult": 1.10, "draw_shift": -0.03, "label": "Friendly"},
}

def get_context_info(context_type: str) -> dict:
    return CONTEXT_FACTORS.get(context_type, CONTEXT_FACTORS["league"])


class MonteCarloSimulator:
    """Monte Carlo match simulator with tau-corrected Poisson + match context."""

    def __init__(self, home_gamma=0.2, rho=-0.13):
        self.gamma = home_gamma
        self.rho = rho

    def _build_prob_matrix(self, lam, mu, max_goals=10):
        """Build tau-corrected joint probability matrix."""
        dc = DixonColes()
        n = max_goals + 1
        prob_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
                tau = dc.rho_correction(i, j, lam, mu, self.rho)
                prob_matrix[i, j] = max(tau * p, 0)
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total
        return prob_matrix

    def _apply_context(self, prob_matrix, context_type):
        """Adjust probability matrix based on match context.

        For high-stakes matches:
        - Reduce high-scoring outcomes (more cautious play)
        - Increase draw probability slightly
        - Shift probability mass toward 0-0, 1-0, 0-1, 1-1
        """
        ctx = get_context_info(context_type)
        goal_mult = ctx["goal_mult"]
        draw_shift = ctx["draw_shift"]

        if goal_mult == 1.0 and draw_shift == 0.0:
            return prob_matrix

        n = prob_matrix.shape[0]
        adjusted = np.zeros_like(prob_matrix)

        for i in range(n):
            for j in range(n):
                total_goals = i + j
                # Goal multiplier: reduce/increase probability based on total goals
                # Lower goal_mult -> suppress high-scoring, boost low-scoring
                if goal_mult < 1.0:
                    # More cautious: reduce high-scoring, boost low-scoring
                    if total_goals <= 2:
                        adjusted[i, j] = prob_matrix[i, j] * (1 + (1 - goal_mult) * 0.5)
                    elif total_goals <= 4:
                        adjusted[i, j] = prob_matrix[i, j] * goal_mult
                    else:
                        adjusted[i, j] = prob_matrix[i, j] * (goal_mult ** 2)
                else:
                    # More open: boost high-scoring, reduce low-scoring
                    if total_goals <= 1:
                        adjusted[i, j] = prob_matrix[i, j] * (2 - goal_mult)
                    elif total_goals <= 3:
                        adjusted[i, j] = prob_matrix[i, j] * goal_mult
                    else:
                        adjusted[i, j] = prob_matrix[i, j] * (goal_mult ** 1.5)

                # Draw shift: boost/penalize diagonal (i == j)
                if draw_shift != 0 and i == j and i > 0:
                    adjusted[i, j] *= (1 + draw_shift * 3)

        # Normalize
        total = adjusted.sum()
        if total > 0:
            adjusted /= total
        return adjusted

    def run(self, squad_a: dict, squad_b: dict,
            n: int = 1000, home_advantage: bool = True,
            match_context: str = "league") -> dict:
        t0 = time.time()

        att_a, def_a = calc_team_strength(squad_a)
        att_b, def_b = calc_team_strength(squad_b)

        gamma = self.gamma if home_advantage else 0.0
        lam = np.exp(att_a - def_b + gamma)
        mu  = np.exp(att_b - def_a)

        # Build base tau-corrected probability matrix
        prob_matrix = self._build_prob_matrix(lam, mu)

        # Apply match context adjustment
        prob_matrix = self._apply_context(prob_matrix, match_context)

        #  Sample from adjusted joint distribution
        flat = prob_matrix.flatten()
        flat = np.maximum(flat, 0)
        flat /= flat.sum()
        grid_size = prob_matrix.shape[0]

        indices = np.random.choice(len(flat), size=n, p=flat)
        home_goals = indices // grid_size
        away_goals = indices % grid_size

        # Aggregate results
        results = []
        for h, a in zip(home_goals, away_goals):
            if h > a: results.append("H")
            elif a > h: results.append("A")
            else: results.append("D")

        wdl = {
            "home_win": round(results.count("H") / n, 4),
            "draw":     round(results.count("D") / n, 4),
            "away_win": round(results.count("A") / n, 4),
        }

        scores = [f"{h}-{a}" for h, a in zip(home_goals, away_goals)]
        score_counts = Counter(scores)
        score_dist = {s: round(c / n, 4) for s, c in score_counts.most_common(15)}
        most_likely = max(score_counts, key=score_counts.get) if score_counts else "0-0"

        elapsed_ms = round((time.time() - t0) * 1000)
        ctx_info = get_context_info(match_context)

        return {
            "wdl": wdl,
            "avg_goals": {
                "home": round(float(np.mean(home_goals)), 2),
                "away": round(float(np.mean(away_goals)), 2),
                "total": round(float(np.mean(home_goals + away_goals)), 2),
            },
            "expected_goals": {
                "home": round(float(lam), 2),
                "away": round(float(mu), 2),
            },
            "most_likely_score": most_likely,
            "score_distribution": score_dist,
            "sim_count": n,
            "duration_ms": elapsed_ms,
            "squads": {
                "home": squad_summary(squad_a),
                "away": squad_summary(squad_b),
            },
            "model": "dixon_coles_tau",
            "rho": self.rho,
            "match_context": {
                "type": match_context,
                "label": ctx_info["label"],
                "goal_factor": ctx_info["goal_mult"],
                "draw_shift": ctx_info["draw_shift"],
            },
        }


_simulator = MonteCarloSimulator()

def simulate(squad_a, squad_b, n=1000, home_advantage=True, match_context="league"):
    return _simulator.run(squad_a, squad_b, n, home_advantage, match_context)
