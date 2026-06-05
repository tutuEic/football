# -*- coding: utf-8 -*-
"""
Dixon-Coles model trained on international football matches.

Based on:
- Dixon & Coles (1997): "Modelling Association Football Scores"
- Groll et al. (2015): "Prediction of major international soccer tournaments"

Data cleaning:
- Normalize team names (China -> China PR, etc.)
- Exclude non-FIFA teams from friendlies
- Only include matches between verified FIFA teams
"""
import json
import os
import sys
import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query

MODEL_DIR = Path(__file__).resolve().parent.parent / 'wc_models'
MODEL_DIR.mkdir(exist_ok=True)

# ============================================================
# Data Cleaning
# ============================================================

# Team name normalization
TEAM_NAME_MAP = {
    'China':                    'China PR',
    'Bosnia-Herzegovina':       'Bosnia and Herzegovina',
    'Democratic Republic of the Congo': 'DR Congo',
    'Côte d\'Ivoire':           'Ivory Coast',
    'Cote d\'Ivoire':           'Ivory Coast',
    'Korea Republic':           'South Korea',
    'IR Iran':                  'Iran',
    'Turkiye':                  'Turkey',
    'Cabo Verde':               'Cape Verde',
    'USA':                      'United States',
}

# Non-FIFA teams (from data analysis)
NON_FIFA_TEAMS = {
    'Abkhazia', 'Alderney', 'Barawa', 'Basque Country', 'Cascadia',
    'Catalonia', 'Chagos Islands', 'Corsica', 'Donetsk PR',
    'East Turkestan', 'Elba Island', 'Ellan Vannin', 'Franconia',
    'Galicia', 'Greenland', 'Jersey', 'Kernow', 'Luhansk PR',
    'Monaco', 'Occitania', 'Padania', 'Panjab', 'Parishes of Jersey',
    'Raetia', 'Romani people', 'Ryūkyū', 'Saint Barthélemy',
    'Saint Helena', 'Sealand', 'Seborga', 'Somaliland', 'South Ossetia',
    'Surrey', 'Székely Land', 'Tamil Eelam', 'Tibet', 'Ticino',
    'United Koreans in Japan', 'Vatican City', 'West Papua',
    'Ynys Môn', 'Yorkshire',
}


def normalize_team(name):
    """Normalize team name."""
    return TEAM_NAME_MAP.get(name, name)


class InternationalDixonColes:
    """Dixon-Coles model for international football with analytical gradient."""

    def __init__(self):
        self.teams = []
        self.params = {}
        self.fitted = False

    def _rho_tau(self, x, y, lam, mu, rho):
        if x == 0 and y == 0:
            tau = max(1 - lam * mu * rho, 1e-10)
            dtau_dlam = -mu * rho
            dtau_dmu  = -lam * rho
        elif x == 0 and y == 1:
            tau = 1 + lam * rho
            dtau_dlam = rho
            dtau_dmu  = 0
        elif x == 1 and y == 0:
            tau = 1 + mu * rho
            dtau_dlam = 0
            dtau_dmu  = rho
        elif x == 1 and y == 1:
            tau = max(1 - rho, 1e-10)
            dtau_dlam = 0
            dtau_dmu  = 0
        else:
            tau = 1.0
            dtau_dlam = 0
            dtau_dmu  = 0
        return tau, dtau_dlam, dtau_dmu

    def ll_and_grad(self, params, matches, n_teams):
        attack  = params[:n_teams]
        defence = params[n_teams:2*n_teams]
        rho     = params[-2]
        gamma   = params[-1]

        g_attack  = np.zeros(n_teams)
        g_defence = np.zeros(n_teams)
        g_rho = 0.0
        g_gamma = 0.0

        ll = 0.0
        reg = 0.005 * (np.sum(attack**2) + np.sum(defence**2))

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

        g_attack  -= 2 * 0.005 * attack
        g_defence -= 2 * 0.005 * defence

        grad = np.concatenate([g_attack, g_defence, [g_rho, g_gamma]])
        return -(ll - reg), -grad

    def fit(self, matches, max_iter=2000):
        all_teams = set()
        for m in matches:
            all_teams.add(m['home'])
            all_teams.add(m['away'])
        self.teams = sorted(all_teams)
        n_teams = len(self.teams)
        team_idx = {t: i for i, t in enumerate(self.teams)}

        indexed = []
        for m in matches:
            indexed.append({
                'h':  team_idx[m['home']],
                'a':  team_idx[m['away']],
                'hg': int(m['home_goals']),
                'ag': int(m['away_goals']),
                'w':  float(m.get('weight', 1.0)),
            })

        print(f"Training on {len(indexed)} matches, {n_teams} teams ...")

        x0 = np.zeros(2 * n_teams + 2)
        x0[-2] = -0.10
        x0[-1] = 0.20

        # Pin first team attack and defence at 0 for identifiability.
        # Without this, the parameter space has a translation degree of freedom:
        # attack[i]+c, defence[i]-c gives the same likelihood for all c.
        from scipy.optimize import Bounds
        bounds = Bounds(
            lb=[-3.0] * n_teams + [-3.0] * n_teams + [-0.5, -1.0],
            ub=[3.0] * n_teams + [3.0] * n_teams + [0.5, 1.0],
        )
        x0[0] = 0.0
        x0[n_teams] = 0.0
        bounds.lb[0] = -0.001; bounds.ub[0] = 0.001
        bounds.lb[n_teams] = -0.001; bounds.ub[n_teams] = 0.001

        result = minimize(
            self.ll_and_grad, x0,
            args=(indexed, n_teams),
            method='L-BFGS-B', jac=True,
            bounds=bounds,
            options={'maxiter': max_iter, 'ftol': 1e-7}
        )

        attack  = dict(zip(self.teams, result.x[:n_teams]))
        defence = dict(zip(self.teams, result.x[n_teams:2*n_teams]))

        self.params = {
            'attack':  {k: round(float(v), 4) for k, v in attack.items()},
            'defence': {k: round(float(v), 4) for k, v in defence.items()},
            'rho':    round(float(result.x[-2]), 4),
            'gamma':  round(float(result.x[-1]), 4),
            'log_likelihood': round(float(-result.fun), 2),
            'n_matches': len(indexed),
            'n_teams': n_teams,
        }
        self.fitted = True

        print(f"Done: LL={self.params['log_likelihood']:.2f}  "
              f"rho={self.params['rho']:.4f}  gamma={self.params['gamma']:.4f}  "
              f"iters={result.nit}")
        return True

    def get_match_probs(self, home_team, away_team):
        if not self.fitted:
            raise RuntimeError("Model not fitted")
        if home_team not in self.teams or away_team not in self.teams:
            return self._default_probs()

        att_h = self.params['attack'][home_team]
        def_h = self.params['defence'][home_team]
        att_a = self.params['attack'][away_team]
        def_a = self.params['defence'][away_team]
        gamma = self.params['gamma']
        rho   = self.params['rho']

        lam = np.exp(att_h + def_a + gamma)
        mu  = np.exp(att_a + def_h)

        n = 9
        prob = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
                if i == 0 and j == 0:
                    tau = max(1 - lam * mu * rho, 1e-10)
                elif i == 0 and j == 1:
                    tau = 1 + lam * rho
                elif i == 1 and j == 0:
                    tau = 1 + mu * rho
                elif i == 1 and j == 1:
                    tau = max(1 - rho, 1e-10)
                else:
                    tau = 1.0
                prob[i, j] = max(tau * p, 0)

        total = prob.sum()
        if total > 0:
            prob /= total

        home_win = float(sum(prob[i, j] for i in range(n) for j in range(n) if i > j))
        draw     = float(sum(prob[i, i] for i in range(n)))
        away_win = float(sum(prob[i, j] for i in range(n) for j in range(n) if i < j))
        best = np.unravel_index(prob.argmax(), prob.shape)
        over_25 = float(sum(prob[i, j] for i in range(n) for j in range(n) if i + j > 2))

        return {
            'home_win': round(home_win, 4),
            'draw':     round(draw, 4),
            'away_win': round(away_win, 4),
            'expected_goals': {'home': round(float(lam), 2), 'away': round(float(mu), 2)},
            'most_likely_score': f"{best[0]}-{best[1]}",
            'over_25': round(over_25, 4),
        }

    def _default_probs(self):
        return {
            'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30,
            'expected_goals': {'home': 1.3, 'away': 1.1},
            'most_likely_score': '1-0', 'over_25': 0.55,
        }

    def save(self, filepath=None):
        if filepath is None:
            filepath = MODEL_DIR / 'dc_intl_latest.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'model_type': 'international_dixon_coles',
                'teams': self.teams,
                'params': self.params,
            }, f, indent=2, ensure_ascii=False)
        print(f"Saved to {filepath}")
        return filepath

    def load(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.teams = data['teams']
        self.params = data['params']
        self.fitted = True


def load_training_data(start_date='2014-01-01'):
    """Load international matches with data cleaning."""
    # Step 1: Get FIFA teams from competitive matches
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
    print(f"FIFA teams: {len(fifa_teams)}")

    # Step 2: Load all matches
    rows = query(
        "SELECT home_club_name as home, away_club_name as away, "
        "home_club_goals as home_goals, away_club_goals as away_goals, "
        "competition_id, date "
        "FROM tm_games "
        "WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN','WCQL','EUCON','AFQL','ACQL','UNL','CNL','GC','FR') "
        "AND home_club_goals IS NOT NULL AND date >= %s ORDER BY date",
        [start_date], db='football_pred'
    )

    comp_weight = {
        'FIWC': 1.0, 'EURO': 0.95, 'COPA': 0.95, 'AFAC': 0.90, 'AFCN': 0.85,
        'WCQL': 0.75, 'EUCON': 0.70, 'AFQL': 0.65, 'ACQL': 0.60,
        'UNL': 0.70, 'CNL': 0.60, 'GC': 0.65, 'FR': 0.40,
    }
    decay_lambda = math.log(2) / 730
    today = date.today()

    matches = []
    skipped = 0
    for r in rows:
        home = normalize_team(r['home'])
        away = normalize_team(r['away'])
        comp = r['competition_id']

        # Filter: both teams must be FIFA members
        if home not in fifa_teams or away not in fifa_teams:
            skipped += 1
            continue

        # Filter: no non-FIFA teams
        if home in NON_FIFA_TEAMS or away in NON_FIFA_TEAMS:
            skipped += 1
            continue

        m_date = r['date']
        if isinstance(m_date, str):
            m_date = datetime.strptime(m_date, '%Y-%m-%d').date()

        days_ago = (today - m_date).days
        recency = math.exp(-decay_lambda * days_ago)
        cw = comp_weight.get(comp, 0.5)
        weight = cw * recency

        matches.append({
            'home': home, 'away': away,
            'home_goals': int(r['home_goals']),
            'away_goals': int(r['away_goals']),
            'competition': comp, 'date': str(m_date),
            'weight': round(weight, 4),
        })

    print(f"Loaded {len(matches)} matches (skipped {skipped} non-FIFA/noise)")
    return matches


def train_and_save():
    print("=" * 60)
    print("Training International Dixon-Coles Model (cleaned data)")
    print("=" * 60)
    matches = load_training_data()
    model = InternationalDixonColes()
    model.fit(matches)
    model.save()
    return model


if __name__ == '__main__':
    model = train_and_save()

    print("\n=== Sample Predictions ===")
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
