# -*- coding: utf-8 -*-
"""
Dixon-Coles + Elo Prior (Bayesian DC)

Combines data-driven DC parameters with Elo-based priors.
Teams with few matches get pulled toward Elo estimates.
Teams with many matches are determined mainly by match data.

Based on:
- Dixon & Coles (1997)
- Baio & Blangiardo (2010): Bayesian hierarchical model
- Groll et al. (2015): World Cup prediction with covariates
"""
import json
import os
import sys
import numpy as np
from scipy.stats import poisson
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_dc_international import (
    InternationalDixonColes, load_training_data,
    normalize_team, NON_FIFA_TEAMS, TEAM_NAME_MAP,
    MODEL_DIR,
)

# ============================================================
# Elo Prior Computation
# ============================================================

def compute_elo_priors():
    """
    Compute Elo-based attack/defence priors for all FIFA teams.
    
    Returns dict: team -> {'attack_prior': float, 'defence_prior': float, 'weight': float}
    """
    from engine.wc_elo_adapter import analyze_squad_elo
    
    # Get all FIFA teams
    rows = query(
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
    
    teams = [normalize_team(r['team']) for r in rows]
    teams = [t for t in teams if t not in NON_FIFA_TEAMS]
    
    priors = {}
    computed = 0
    failed = 0
    
    for team in teams:
        try:
            analysis = analyze_squad_elo(team)
            # Convert Elo scores to DC parameters
            # attack_quality (0-99) -> attack parameter (centered around 0)
            # Typical DC attack range: -2 to +2
            att_q = analysis['attack_quality']
            def_q = analysis['defense_quality']
            
            # Scale: 70 = average, each 10 points = ~0.3 in DC params
            attack_prior = (att_q - 70) / 30.0
            defence_prior = -(def_q - 70) / 30.0  # Negative: better defence = lower goals
            
            # Prior weight based on squad data quality
            # More players with Elo data = stronger prior
            n_players = analysis.get('squad_size', 0)
            weight = min(n_players / 20.0, 1.0)  # Full weight at 20+ players
            
            priors[team] = {
                'attack_prior': round(attack_prior, 4),
                'defence_prior': round(defence_prior, 4),
                'weight': round(weight, 4),
                'elo_bonus': analysis['elo_bonus'],
            }
            computed += 1
        except Exception as e:
            # No Elo data - use neutral prior
            priors[team] = {
                'attack_prior': 0.0,
                'defence_prior': 0.0,
                'weight': 0.0,
                'elo_bonus': 0.0,
            }
            failed += 1
    
    print(f"Elo priors: {computed} computed, {failed} fallback")
    return priors


class BayesianDixonColes(InternationalDixonColes):
    """
    Dixon-Coles with Elo-based Bayesian priors.
    
    The log-likelihood includes a prior term:
        L_total = L_data + lambda * L_prior
    
    where L_prior penalizes deviation from Elo-based estimates.
    lambda is per-team: teams with fewer matches get stronger prior.
    """
    
    def __init__(self):
        super().__init__()
        self.priors = {}
        self.prior_lambda = 0.5  # Global prior strength
    
    def set_priors(self, priors, prior_lambda=0.5):
        """Set Elo-based priors."""
        self.priors = priors
        self.prior_lambda = prior_lambda
    
    def ll_and_grad(self, params, matches, n_teams):
        """Log-likelihood with Elo prior."""
        attack  = params[:n_teams]
        defence = params[n_teams:2*n_teams]
        rho     = params[-2]
        gamma   = params[-1]

        g_attack  = np.zeros(n_teams)
        g_defence = np.zeros(n_teams)
        g_rho = 0.0
        g_gamma = 0.0

        ll = 0.0
        
        # === Data likelihood (same as parent) ===
        for m in matches:
            hi = m['h']
            ai = m['a']
            x  = m['hg']
            y  = m['ag']
            w  = m['w']

            a_h = attack[hi]
            d_h = defence[hi]
            a_a = attack[ai]
            d_a = defence[ai]

            lam = np.exp(a_h + d_a + gamma)
            mu  = np.exp(a_a + d_h)

            px = poisson.pmf(x, lam)
            py = poisson.pmf(y, mu)

            tau, dtau_dlam, dtau_dmu = self._rho_tau(x, y, lam, mu, rho)
            prob = max(tau * px * py, 1e-10)
            ll += w * np.log(prob)

            if lam > 0:
                dpx_dlam = px * (x / lam - 1)
            else:
                dpx_dlam = 0
            if mu > 0:
                dpy_dmu = py * (y / mu - 1)
            else:
                dpy_dmu = 0

            d_logp_dlam = (dtau_dlam * px * py + tau * dpx_dlam * py) / prob
            d_logp_dmu  = (dtau_dmu * px * py + tau * px * dpy_dmu) / prob

            w_dlam = w * d_logp_dlam
            w_dmu  = w * d_logp_dmu

            g_attack[hi]  += w_dlam * lam
            g_defence[ai] += w_dlam * lam
            g_attack[ai]  += w_dmu * mu
            g_defence[hi] += w_dmu * mu
            g_gamma       += w_dlam * lam

            if x == 0 and y == 0:
                dtau_drho = -lam * mu
            elif x == 0 and y == 1:
                dtau_drho = lam
            elif x == 1 and y == 0:
                dtau_drho = mu
            elif x == 1 and y == 1:
                dtau_drho = -1
            else:
                dtau_drho = 0

            g_rho += w * (dtau_drho * px * py) / prob

        # === Elo Prior term ===
        prior_ll = 0.0
        for i, team in enumerate(self.teams):
            if team in self.priors:
                p = self.priors[team]
                w_prior = p['weight'] * self.prior_lambda
                
                # Attack prior: penalize deviation from Elo estimate
                att_diff = attack[i] - p['attack_prior']
                prior_ll -= w_prior * att_diff**2
                g_attack[i] -= 2 * w_prior * att_diff
                
                # Defence prior
                def_diff = defence[i] - p['defence_prior']
                prior_ll -= w_prior * def_diff**2
                g_defence[i] -= 2 * w_prior * def_diff

        grad = np.concatenate([g_attack, g_defence, [g_rho, g_gamma]])
        return -(ll + prior_ll), -grad
    
    def save(self, filepath=None):
        if filepath is None:
            filepath = MODEL_DIR / 'bayes_dc_intl_latest.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'model_type': 'bayesian_dixon_coles',
                'teams': self.teams,
                'params': self.params,
                'priors': self.priors,
                'prior_lambda': self.prior_lambda,
            }, f, indent=2, ensure_ascii=False)
        print(f"Saved to {filepath}")
        return filepath
    
    def load(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.teams = data['teams']
        self.params = data['params']
        self.priors = data.get('priors', {})
        self.prior_lambda = data.get('prior_lambda', 0.5)
        self.fitted = True


def train_bayesian_dc(prior_lambda=0.5):
    """Train Bayesian DC with Elo priors."""
    print("=" * 60)
    print("Training Bayesian Dixon-Coles (Elo Prior)")
    print("=" * 60)
    
    # Load matches
    matches = load_training_data()
    
    # Compute Elo priors
    print("\nComputing Elo priors ...")
    priors = compute_elo_priors()
    
    # Train model
    model = BayesianDixonColes()
    model.set_priors(priors, prior_lambda)
    model.fit(matches)
    model.save()
    
    return model


if __name__ == '__main__':
    model = train_bayesian_dc()
    
    print("\n=== Predictions ===")
    tests = [
        ('Brazil', 'Croatia'), ('France', 'Morocco'),
        ('Argentina', 'Saudi Arabia'), ('England', 'Iran'),
        ('Germany', 'Japan'), ('Spain', 'Italy'),
        ('France', 'Brazil'), ('Argentina', 'France'),
    ]
    for home, away in tests:
        pred = model.get_match_probs(home, away)
        print(f"  {home:20s} vs {away:20s}  "
              f"WDL: {pred['home_win']:.1%}/{pred['draw']:.1%}/{pred['away_win']:.1%}  "
              f"xG: {pred['expected_goals']['home']:.2f}-{pred['expected_goals']['away']:.2f}")
