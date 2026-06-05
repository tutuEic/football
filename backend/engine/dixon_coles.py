# -*- coding: utf-8 -*-
"""
# Dixon-Coles football prediction model
Based on Dixon & Coles (1997) paper
# Cleaned up and integrated into project (no external dependencies)
"""
import numpy as np
from scipy.optimize import minimize, Bounds
from scipy.stats import poisson


class DixonColes:
    """
    # Dixon-Coles football prediction model.

    Parameters:
        alpha_i: team i attack strength
        beta_i: team i defence strength
        gamma: home advantage
        rho: low-score correlation parameter
    """

    def __init__(self):
        self.teams = []
        self.params = {}
        self.fitted = False

    def rho_correction(self, x, y, lam, mu, rho):
        """Dixon-Coles tau correction factor for low-score outcomes."""
        if x == 0 and y == 0:
            return max(1 - lam * mu * rho, 1e-10)
        elif x == 0 and y == 1:
            return 1 + lam * rho
        elif x == 1 and y == 0:
            return 1 + mu * rho
        elif x == 1 and y == 1:
            return max(1 - rho, 1e-10)
        else:
            return 1.0

    def log_likelihood(self, params, matches):
        """Negative log-likelihood (objective for minimizer)."""
        n_teams = len(self.teams)

        attack = dict(zip(self.teams, params[:n_teams]))
        defence = dict(zip(self.teams, params[n_teams:2 * n_teams]))
        rho, gamma = params[-2:]

        ll = 0
        for match in matches:
            home = match['home']
            away = match['away']
            x = int(match['home_goals'])
            y = int(match['away_goals'])
            w = float(match.get('weight', 1.0))

            lam = np.exp(attack[home] + defence[away] + gamma)
            mu = np.exp(attack[away] + defence[home])

            p_x = poisson.pmf(x, lam)
            p_y = poisson.pmf(y, mu)

            tau = self.rho_correction(x, y, lam, mu, rho)
            prob = max(tau * p_x * p_y, 1e-10)
            ll += w * np.log(prob)

        return -ll

    def fit(self, matches, max_iter=2000):
        """
        # Train the model.

        Args:
            matches: list of dicts with keys: home, away, home_goals, away_goals
        """
        all_teams = set()
        for m in matches:
            all_teams.add(m['home'])
            all_teams.add(m['away'])
        self.teams = sorted(all_teams)
        n_teams = len(self.teams)

        print(f'Training Dixon-Coles on {len(matches)} matches, {n_teams} teams')

        # Average goals for initial gamma estimate
        avg_goals = np.mean([m['home_goals'] for m in matches])
        init_gamma = np.log(avg_goals) if avg_goals > 0 else 0.25

        # Initial parameters
        x0 = np.zeros(2 * n_teams + 2)
        x0[-1] = init_gamma  # gamma
        x0[-2] = -0.13       # rho (typical starting value)

        # Identifiability: constrain first team attack to 0
        bounds = Bounds(
            lb=[-3.0] * n_teams + [-3.0] * n_teams + [-0.5, -1.0],
            ub=[3.0] * n_teams + [3.0] * n_teams + [0.5, 1.0],
        )
        x0[0] = 0.0  # fix first team attack (identifiability)
        x0[n_teams] = 0.0  # fix first team defence (identifiability)
        bounds.lb[0] = -0.001; bounds.ub[0] = 0.001
        bounds.lb[n_teams] = -0.001; bounds.ub[n_teams] = 0.001

        result = minimize(
            self.log_likelihood, x0,
            args=(matches,),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': max_iter, 'disp': False},
        )

        if not result.success:
            print(f'Warning: optimization did not converge: {result.message}')

        # Extract parameters
        attack = dict(zip(self.teams, result.x[:n_teams]))
        defence = dict(zip(self.teams, result.x[n_teams:2 * n_teams]))
        rho = float(result.x[-2])
        gamma = float(result.x[-1])

        self.params = {
            'attack': attack,
            'defence': defence,
            'rho': rho,
            'gamma': gamma,
            'log_likelihood': float(-result.fun),
        }
        self.fitted = True
        return True

    def get_match_probs(self, home_team, away_team, max_goals=10):
        """
        # Compute match outcome probabilities using tau-corrected Poisson.
        """
        if not self.fitted:
            raise ValueError('Model not fitted')

        att_h = self.params['attack'].get(home_team, 0.0)
        def_h = self.params['defence'].get(home_team, 0.0)
        att_a = self.params['attack'].get(away_team, 0.0)
        def_a = self.params['defence'].get(away_team, 0.0)
        rho = self.params['rho']
        gamma = self.params['gamma']

        lam = np.exp(att_h + def_a + gamma)  # home expected goals
        mu = np.exp(att_a + def_h)            # away expected goals

        #  Build probability matrix with tau correction
        n = max_goals + 1
        prob_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
                tau = self.rho_correction(i, j, lam, mu, rho)
                prob_matrix[i, j] = max(tau * p, 0)

        # Normalize
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total

        home_win = np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i > j])
        draw = np.sum([prob_matrix[i, i] for i in range(n)])
        away_win = np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i < j])

        return {
            'home_win': float(home_win),
            'draw': float(draw),
            'away_win': float(away_win),
            'expected_goals': {'home': float(lam), 'away': float(mu)},
            'prob_matrix': prob_matrix,
        }

    def sample_score(self, home_team, away_team, n_samples=1):
        """
        # Sample scores using rejection sampling with tau correction. This correctly accounts for low-score correlation.
        """
        if not self.fitted:
            raise ValueError('Model not fitted')

        result = self.get_match_probs(home_team, away_team)
        prob_matrix = result['prob_matrix']
        n = prob_matrix.shape[0]

        #  Flatten and normalize for sampling
        flat = prob_matrix.flatten()
        flat = np.maximum(flat, 0)
        flat /= flat.sum()

        #  Sample from the joint distribution
        indices = np.random.choice(len(flat), size=n_samples, p=flat)
        home_goals = indices // n
        away_goals = indices % n

        return home_goals, away_goals

    def get_team_strength(self, team):
        """Get team attack/defence strength (exponentiated for interpretability)."""
        if not self.fitted or team not in self.params['attack']:
            return None
        return {
            'attack': float(np.exp(self.params['attack'][team])),
            'defence': float(np.exp(-self.params['defence'][team])),
        }
