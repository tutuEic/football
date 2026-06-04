# -*- coding: utf-8 -*-
"""
Bayesian Dixon-Coles Model (P0-1)
=================================
Replaces MLE with Bayesian estimation via Laplace approximation.

Key improvements over standard DC:
1. Priors provide shrinkage: teams with few matches get pulled toward league average
2. Uncertainty quantification: predictions come with credible intervals
3. More robust parameter estimates for mid-table teams

References:
- Baio & Blangiardo (2010) "Bayesian hierarchical model for football results"
- Dixon & Coles (1997) "Modelling Association Football Scores"
"""
import json
import math
import numpy as np
from pathlib import Path
from scipy.optimize import minimize
from scipy.stats import poisson, norm
from scipy.linalg import inv
from collections import defaultdict


class BayesianDixonColes:
    """
    Bayesian Dixon-Coles with Laplace approximation.
    
    Model:
        home_goals ~ Poisson(lambda)
        away_goals ~ Poisson(mu)
        where:
            lambda = exp(alpha_home + beta_away + gamma)
            mu     = exp(alpha_away + beta_home)
        
        Priors:
            alpha_i ~ Normal(0, sigma_a^2)    # attack strength
            beta_i  ~ Normal(0, sigma_d^2)    # defence strength
            gamma   ~ Normal(mu_gamma, sg^2)  # home advantage
            rho     ~ Normal(mu_rho, sr^2)    # low-score correlation
    """

    def __init__(self, sigma_attack=0.5, sigma_defence=0.3,
                 prior_gamma=(0.25, 0.15), prior_rho=(-0.13, 0.10)):
        self.sigma_attack = sigma_attack     # prior std for attack
        self.sigma_defence = sigma_defence   # prior std for defence
        self.prior_gamma = prior_gamma       # (mean, std) for gamma
        self.prior_rho = prior_rho           # (mean, std) for rho
        
        self.teams = []
        self.n_teams = 0
        self.posterior_mean = None
        self.posterior_cov = None
        self.fitted = False
        
        # Results
        self.params = {}

    def _rho_correction(self, x, y, lam, mu, rho):
        """Dixon-Coles tau correction."""
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

    def _neg_log_posterior(self, theta, matches, weights=None):
        """Negative log-posterior = -log-likelihood - log-prior."""
        n = self.n_teams
        
        # Extract parameters
        attack = theta[:n]
        defence = theta[n:2*n]
        gamma = theta[2*n]
        rho = theta[2*n + 1]
        
        # === Log-prior ===
        log_prior = 0.0
        # Attack priors (skip first team, fixed at 0 for identifiability)
        log_prior += np.sum(norm.logpdf(attack[1:], 0, self.sigma_attack))
        # Defence priors
        log_prior += np.sum(norm.logpdf(defence, 0, self.sigma_defence))
        # Gamma prior
        log_prior += norm.logpdf(gamma, *self.prior_gamma)
        # Rho prior
        log_prior += norm.logpdf(rho, *self.prior_rho)
        
        # === Log-likelihood ===
        log_lik = 0.0
        for i, m in enumerate(matches):
            h_idx = m['home_idx']
            a_idx = m['away_idx']
            hg = int(m['home_goals'])
            ag = int(m['away_goals'])
            w = float(weights[i]) if weights is not None else 1.0
            
            lam = np.exp(attack[h_idx] + defence[a_idx] + gamma)
            mu = np.exp(attack[a_idx] + defence[h_idx])
            
            p_x = poisson.pmf(hg, max(lam, 1e-10))
            p_y = poisson.pmf(ag, max(mu, 1e-10))
            tau = self._rho_correction(hg, ag, lam, mu, rho)
            prob = max(tau * p_x * p_y, 1e-10)
            
            log_lik += w * np.log(prob)
        
        return -(log_lik + log_prior)

    def _neg_log_posterior_grad(self, theta, matches, weights=None):
        """Gradient of negative log-posterior (numerical for now)."""
        # Use finite differences
        eps = 1e-5
        grad = np.zeros_like(theta)
        f0 = self._neg_log_posterior(theta, matches, weights)
        for i in range(len(theta)):
            theta_plus = theta.copy()
            theta_plus[i] += eps
            grad[i] = (self._neg_log_posterior(theta_plus, matches, weights) - f0) / eps
        return grad

    def fit(self, matches, max_iter=3000):
        """
        Fit the Bayesian DC model using Laplace approximation.
        
        Args:
            matches: list of dicts with 'home', 'away', 'home_goals', 'away_goals'
                     Optional: 'weight' for time-weighted training
        """
        # Build team index
        all_teams = set()
        for m in matches:
            all_teams.add(m['home'])
            all_teams.add(m['away'])
        self.teams = sorted(all_teams)
        self.n_teams = len(self.teams)
        team_idx = {t: i for i, t in enumerate(self.teams)}
        
        # Add indices to matches
        indexed = []
        weights = []
        for m in matches:
            indexed.append({
                'home_idx': team_idx[m['home']],
                'away_idx': team_idx[m['away']],
                'home_goals': m['home_goals'],
                'away_goals': m['away_goals'],
            })
            weights.append(float(m.get('weight', 1.0)))
        
        weights = np.array(weights)
        n = self.n_teams
        
        print(f"Bayesian DC: {len(matches)} matches, {n} teams")
        print(f"  Priors: sigma_a={self.sigma_attack}, sigma_d={self.sigma_defence}")
        print(f"  gamma~N{self.prior_gamma}, rho~N{self.prior_rho}")
        
        # === Step 1: Find MAP estimate (posterior mode) ===
        avg_goals = np.mean([m['home_goals'] for m in matches])
        init_gamma = math.log(avg_goals) if avg_goals > 0 else 0.25
        
        # Start from MLE-like estimate
        x0 = np.zeros(2 * n + 2)
        x0[2*n] = init_gamma      # gamma
        x0[2*n + 1] = -0.13       # rho
        
        # Bounds
        bounds = [(-3.0, 3.0)] * (2 * n) + [(-1.0, 1.0), (-0.5, 0.5)]
        # Fix first team attack at 0 (identifiability)
        x0[0] = 0.0
        bounds[0] = (-0.001, 0.001)
        
        result = minimize(
            self._neg_log_posterior,
            x0,
            args=(indexed, weights),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': max_iter, 'disp': False},
        )
        
        map_estimate = result.x
        print(f"  MAP converged: {result.success}, NLL={result.fun:.2f}")
        
        # === Step 2: Laplace approximation (diagonal Hessian) ===
        # Use diagonal Hessian for speed (k params -> full Hessian too slow)
        eps = 1e-4
        k = len(map_estimate)
        f0 = self._neg_log_posterior(map_estimate, indexed, weights)
        hess_diag = np.zeros(k)
        
        for i in range(k):
            ei = np.zeros(k)
            ei[i] = eps
            fp = self._neg_log_posterior(map_estimate + ei, indexed, weights)
            fm = self._neg_log_posterior(map_estimate - ei, indexed, weights)
            hess_diag[i] = (fp - 2*f0 + fm) / (eps * eps)
        
        hess_diag = np.maximum(hess_diag, 1e-4)
        posterior_cov = np.diag(1.0 / hess_diag)
        print("  Laplace approximation OK (diagonal)")
        self.posterior_mean = map_estimate
        self.posterior_cov = posterior_cov
        
        # Extract parameters
        attack = dict(zip(self.teams, map_estimate[:n]))
        defence = dict(zip(self.teams, map_estimate[n:2*n]))
        gamma = float(map_estimate[2*n])
        rho = float(map_estimate[2*n + 1])
        
        # Posterior uncertainties
        attack_std = dict(zip(self.teams, np.sqrt(np.maximum(np.diag(posterior_cov[:n, :n]), 0))))
        defence_std = dict(zip(self.teams, np.sqrt(np.maximum(np.diag(posterior_cov[n:2*n, n:2*n]), 0))))
        gamma_std = float(np.sqrt(max(posterior_cov[2*n, 2*n], 0)))
        rho_std = float(np.sqrt(max(posterior_cov[2*n+1, 2*n+1], 0)))
        
        self.params = {
            'attack': attack,
            'defence': defence,
            'gamma': gamma,
            'rho': rho,
            'attack_std': attack_std,
            'defence_std': defence_std,
            'gamma_std': gamma_std,
            'rho_std': rho_std,
            'log_posterior': float(-result.fun),
            'n_matches': len(matches),
            'n_teams': n,
        }
        self.fitted = True
        
        # Print summary
        print(f"  gamma={gamma:.4f} +/- {gamma_std:.4f}")
        print(f"  rho={rho:.4f} +/- {rho_std:.4f}")
        
        return True

    def get_match_probs(self, home_team, away_team, max_goals=10):
        """
        Compute match outcome probabilities.
        Returns point estimate + uncertainty via posterior predictive.
        """
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        att_h = self.params['attack'].get(home_team, 0.0)
        def_h = self.params['defence'].get(home_team, 0.0)
        att_a = self.params['attack'].get(away_team, 0.0)
        def_a = self.params['defence'].get(away_team, 0.0)
        rho = self.params['rho']
        gamma = self.params['gamma']
        
        lam = np.exp(att_h + def_a + gamma)
        mu = np.exp(att_a + def_h)
        
        # Point estimate probabilities
        n = max_goals + 1
        prob_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
                tau = self._rho_correction(i, j, lam, mu, rho)
                prob_matrix[i, j] = max(tau * p, 0)
        
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total
        
        home_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i > j]))
        draw = float(np.sum([prob_matrix[i, i] for i in range(n)]))
        away_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i < j]))
        
        # === Uncertainty via Monte Carlo from posterior ===
        n_samples = 200
        hw_samples = []
        dw_samples = []
        aw_samples = []
        
        for _ in range(n_samples):
            # Sample from posterior
            theta_sample = np.random.multivariate_normal(self.posterior_mean, self.posterior_cov)
            n_t = self.n_teams
            
            s_att_h = theta_sample[self.teams.index(home_team)] if home_team in self.teams else 0.0
            s_def_h = theta_sample[n_t + self.teams.index(home_team)] if home_team in self.teams else 0.0
            s_att_a = theta_sample[self.teams.index(away_team)] if away_team in self.teams else 0.0
            s_def_a = theta_sample[n_t + self.teams.index(away_team)] if away_team in self.teams else 0.0
            s_gamma = theta_sample[2*n_t]
            s_rho = theta_sample[2*n_t + 1]
            
            s_lam = np.exp(s_att_h + s_def_a + s_gamma)
            s_mu = np.exp(s_att_a + s_def_h)
            
            s_hw = 0; s_dw = 0; s_aw = 0
            for ii in range(min(n, 8)):
                for jj in range(min(n, 8)):
                    p = poisson.pmf(ii, max(s_lam, 1e-10)) * poisson.pmf(jj, max(s_mu, 1e-10))
                    tau = self._rho_correction(ii, jj, s_lam, s_mu, s_rho)
                    p = max(tau * p, 0)
                    if ii > jj: s_hw += p
                    elif ii == jj: s_dw += p
                    else: s_aw += p
            
            st = s_hw + s_dw + s_aw
            if st > 0:
                hw_samples.append(s_hw / st)
                dw_samples.append(s_dw / st)
                aw_samples.append(s_aw / st)
        
        # Compute credible intervals
        hw_arr = np.array(hw_samples)
        dw_arr = np.array(dw_samples)
        aw_arr = np.array(aw_samples)
        
        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4),
            'expected_goals': {'home': round(float(lam), 2), 'away': round(float(mu), 2)},
            'prob_matrix': prob_matrix,
            'uncertainty': {
                'home_win_ci': (round(float(np.percentile(hw_arr, 5)), 4), round(float(np.percentile(hw_arr, 95)), 4)),
                'draw_ci': (round(float(np.percentile(dw_arr, 5)), 4), round(float(np.percentile(dw_arr, 95)), 4)),
                'away_win_ci': (round(float(np.percentile(aw_arr, 5)), 4), round(float(np.percentile(aw_arr, 95)), 4)),
                'home_win_std': round(float(np.std(hw_arr)), 4),
                'draw_std': round(float(np.std(dw_arr)), 4),
                'away_win_std': round(float(np.std(aw_arr)), 4),
            },
        }

    def get_team_strength(self, team):
        """Get team strength with uncertainty."""
        if not self.fitted or team not in self.params['attack']:
            return None
        return {
            'attack': round(float(np.exp(self.params['attack'][team])), 3),
            'defence': round(float(np.exp(-self.params['defence'][team])), 3),
            'attack_std': round(float(self.params['attack_std'].get(team, 0)), 3),
            'defence_std': round(float(self.params['defence_std'].get(team, 0)), 3),
        }


    def get_match_probs_fast(self, home_team, away_team, max_goals=10):
        """Fast point-estimate prediction (no uncertainty)."""
        if not self.fitted:
            raise ValueError("Model not fitted")
        att_h = self.params['attack'].get(home_team, 0.0)
        def_h = self.params['defence'].get(home_team, 0.0)
        att_a = self.params['attack'].get(away_team, 0.0)
        def_a = self.params['defence'].get(away_team, 0.0)
        rho = self.params['rho']
        gamma = self.params['gamma']
        lam = np.exp(att_h + def_a + gamma)
        mu = np.exp(att_a + def_h)
        n = max_goals + 1
        prob_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
                tau = self._rho_correction(i, j, lam, mu, rho)
                prob_matrix[i, j] = max(tau * p, 0)
        total = prob_matrix.sum()
        if total > 0:
            prob_matrix /= total
        home_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i > j]))
        draw = float(np.sum([prob_matrix[i, i] for i in range(n)]))
        away_win = float(np.sum([prob_matrix[i, j] for i in range(n) for j in range(n) if i < j]))
        return {
            'home_win': round(home_win, 4), 'draw': round(draw, 4), 'away_win': round(away_win, 4),
            'expected_goals': {'home': round(float(lam), 2), 'away': round(float(mu), 2)},
        }

    def save(self, path):
        """Save model to JSON."""
        data = {
            'teams': self.teams,
            'params': {
                k: v if isinstance(v, dict) else float(v)
                for k, v in self.params.items()
            },
            'priors': {
                'sigma_attack': self.sigma_attack,
                'sigma_defence': self.sigma_defence,
                'prior_gamma': list(self.prior_gamma),
                'prior_rho': list(self.prior_rho),
            },
            'posterior_mean': self.posterior_mean.tolist(),
            'posterior_cov_diag': np.diag(self.posterior_cov).tolist(),
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding='utf-8')

    def load(self, path):
        """Load model from JSON."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        self.teams = data['teams']
        self.n_teams = len(self.teams)
        self.params = data['params']
        
        # Restore priors if saved
        if 'priors' in data:
            p = data['priors']
            self.sigma_attack = p.get('sigma_attack', 0.5)
            self.sigma_defence = p.get('sigma_defence', 0.3)
            self.prior_gamma = tuple(p.get('prior_gamma', [0.25, 0.15]))
            self.prior_rho = tuple(p.get('prior_rho', [-0.13, 0.10]))
        
        # Restore posterior (approximate from saved diagonal)
        if 'posterior_mean' in data:
            self.posterior_mean = np.array(data['posterior_mean'])
            if 'posterior_cov_diag' in data:
                self.posterior_cov = np.diag(data['posterior_cov_diag'])
            else:
                self.posterior_cov = np.eye(len(self.posterior_mean)) * 0.01
        
        self.fitted = True
