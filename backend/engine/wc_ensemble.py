# -*- coding: utf-8 -*-
"""
WC Prediction Ensemble - combines multiple models.

Models:
1. Bayesian Dixon-Coles (wc_bayes_dc.py) - trained on 10,436 international matches
2. Poisson Regression (wc_poisson_reg.py) - 23 features, trained on 7,076 matches
3. Elo-Poisson (wc_elo_poisson.py) - no training, cold-start friendly

Ensemble methods:
- Weighted average (default)
- Stacking meta-learner (optional, needs training)
"""
import json
import os
import sys
import time
import hashlib
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.wc_bayes_dc import BayesianDixonColes, MODEL_DIR
from engine.wc_poisson_reg import PoissonRegression
from engine.wc_elo_poisson import predict_elo_poisson
from engine.wc_features import compute_match_features, FEATURE_NAMES
from engine.wc_stacking import StackingEnsemble

# Model weights (can be tuned via cross-validation)
DEFAULT_WEIGHTS = {
    'bayes_dc':    0.40,  # Best overall accuracy
    'poisson_reg': 0.15,  # Reduced - model coefficients have issues
    'elo_poisson': 0.45,  # Elo-based, primary factor
}

# Cache
_cache = {}
_CACHE_TTL = 300  # 5 min


class WCPredictionEnsemble:
    """World Cup prediction ensemble."""
    
    def __init__(self, weights=None):
        self.weights = weights or DEFAULT_WEIGHTS
        self.models = {}
        self._load_models()
    
    def _load_models(self):
        """Load all available models."""
        # Bayesian DC
        try:
            bayes_path = MODEL_DIR / 'bayes_dc_intl_latest.json'
            if bayes_path.exists():
                dc = BayesianDixonColes()
                dc.load(bayes_path)
                self.models['bayes_dc'] = dc
                print(f"Loaded Bayesian DC: {len(dc.teams)} teams")
        except Exception as e:
            print(f"Warning: Could not load Bayesian DC: {e}")
        
        # Poisson Regression
        try:
            poisson_path = MODEL_DIR / 'poisson_intl_latest.json'
            if poisson_path.exists():
                pr = PoissonRegression()
                pr.load(poisson_path)
                self.models['poisson_reg'] = pr
                print(f"Loaded Poisson Regression: {pr.n_features} features")
        except Exception as e:
            print(f"Warning: Could not load Poisson Regression: {e}")
        
        # Elo-Poisson (always available)
        self.models['elo_poisson'] = True  # Just a flag
        print(f"Loaded Elo-Poisson (always available)")
        
        # Stacking meta-learner - DISABLED (model coefficients corrupted)
        # try:
        #     stacking_path = MODEL_DIR / 'stacking_intl_latest.json'
        #     if stacking_path.exists():
        #         stacking = StackingEnsemble()
        #         stacking.load(stacking_path)
        #         self.models['stacking'] = stacking
        #         print(f"Loaded Stacking ensemble")
        # except Exception as e:
        #     print(f"Warning: Could not load Stacking: {e}")
    
    def predict(self, home_team, away_team, context=None):
        """
        Get ensemble prediction.
        
        Returns dict with:
        - wdl: home_win, draw, away_win
        - expected_goals: home, away
        - models: individual model predictions
        - method: 'weighted_avg' or 'stacking'
        """
        cache_key = hashlib.md5(f"{home_team}_{away_team}".encode()).hexdigest()
        if cache_key in _cache:
            ts, data = _cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data
        
        predictions = {}
        
        # 1. Bayesian DC
        if 'bayes_dc' in self.models:
            try:
                pred = self.models['bayes_dc'].get_match_probs(home_team, away_team)
                predictions['bayes_dc'] = {
                    'wdl': [pred['home_win'], pred['draw'], pred['away_win']],
                    'xg': pred['expected_goals'],
                }
            except Exception:
                pass
        
        # 2. Poisson Regression
        if 'poisson_reg' in self.models:
            try:
                features = compute_match_features(home_team, away_team)
                pred = self.models['poisson_reg'].predict(features)
                predictions['poisson_reg'] = {
                    'wdl': [pred['home_win'], pred['draw'], pred['away_win']],
                    'xg': pred['expected_goals'],
                }
            except Exception:
                pass
        
        # 3. Elo-Poisson
        try:
            pred = predict_elo_poisson(home_team, away_team)
            predictions['elo_poisson'] = {
                'wdl': [pred['home_win'], pred['draw'], pred['away_win']],
                'xg': pred['expected_goals'],
            }
        except Exception:
            pass
        
        if not predictions:
            result = {
                'wdl': {'home_win': 0.45, 'draw': 0.25, 'away_win': 0.30},
                'expected_goals': {'home': 1.3, 'away': 1.1},
                'models': {},
                'method': 'fallback',
            }
            _cache[cache_key] = (time.time(), result)
            return result
        
        # Try stacking first
        if 'stacking' in self.models and len(predictions) >= 2:
            try:
                dc_wdl = predictions.get('bayes_dc', {}).get('wdl', [0.45, 0.25, 0.30])
                pr_wdl = predictions.get('poisson_reg', {}).get('wdl', [0.45, 0.25, 0.30])
                ep_wdl = predictions.get('elo_poisson', {}).get('wdl', [0.45, 0.25, 0.30])
                
                # Get Elo diff and cohesion for stacking
                try:
                    from engine.wc_elo_adapter import analyze_squad_elo
                    analysis_h = analyze_squad_elo(home_team)
                    analysis_a = analyze_squad_elo(away_team)
                    elo_diff = (analysis_h.get('elo_bonus', 0) - analysis_a.get('elo_bonus', 0)) / 100.0
                    cohesion_h = analysis_h.get('cohesion', 0.5)
                    cohesion_a = analysis_a.get('cohesion', 0.5)
                except:
                    elo_diff = 0.0
                    cohesion_h = 0.5
                    cohesion_a = 0.5
                
                stacking_pred = self.models['stacking'].predict(dc_wdl, pr_wdl, ep_wdl, elo_diff, cohesion_h, cohesion_a)
                
                # Compute expected goals from weighted base models
                final_xg_h = sum(pred['xg']['home'] for pred in predictions.values()) / len(predictions)
                final_xg_a = sum(pred['xg']['away'] for pred in predictions.values()) / len(predictions)
                
                result = {
                    'wdl': {
                        'home_win': stacking_pred['home_win'],
                        'draw': stacking_pred['draw'],
                        'away_win': stacking_pred['away_win'],
                    },
                    'expected_goals': {
                        'home': round(final_xg_h, 2),
                        'away': round(final_xg_a, 2),
                    },
                    'models': {name: {
                        'wdl': [round(p, 4) for p in pred['wdl']],
                        'xg': pred['xg'],
                    } for name, pred in predictions.items()},
                    'weights': {name: self.weights.get(name, 0) for name in predictions},
                    'method': 'stacking',
                }
                _cache[cache_key] = (time.time(), result)
                return result
            except Exception:
                pass  # Fall through to weighted average
        
        # Weighted average fallback
        final_wdl = [0.0, 0.0, 0.0]
        final_xg_h = 0.0
        final_xg_a = 0.0
        total_weight = 0.0
        
        for name, pred in predictions.items():
            w = self.weights.get(name, 0.33)
            wdl = pred['wdl']
            xg = pred['xg']
            
            for i in range(3):
                final_wdl[i] += wdl[i] * w
            final_xg_h += xg['home'] * w
            final_xg_a += xg['away'] * w
            total_weight += w
        
        if total_weight > 0:
            for i in range(3):
                final_wdl[i] /= total_weight
            final_xg_h /= total_weight
            final_xg_a /= total_weight
        
        # Normalize WDL
        s = sum(final_wdl)
        if s > 0:
            final_wdl = [p / s for p in final_wdl]
        
        result = {
            'wdl': {
                'home_win': round(final_wdl[0], 4),
                'draw': round(final_wdl[1], 4),
                'away_win': round(final_wdl[2], 4),
            },
            'expected_goals': {
                'home': round(final_xg_h, 2),
                'away': round(final_xg_a, 2),
            },
            'models': {name: {
                'wdl': [round(p, 4) for p in pred['wdl']],
                'xg': pred['xg'],
            } for name, pred in predictions.items()},
            'weights': {name: self.weights.get(name, 0) for name in predictions},
            'method': 'weighted_avg',
        }
        
        _cache[cache_key] = (time.time(), result)
        return result


# Singleton
_ensemble = None


def get_ensemble():
    """Get or create ensemble singleton."""
    global _ensemble
    if _ensemble is None:
        _ensemble = WCPredictionEnsemble()
    return _ensemble


def predict_wc_match(home_team, away_team, context=None):
    """Module-level prediction function."""
    return get_ensemble().predict(home_team, away_team, context)


if __name__ == '__main__':
    print("=" * 60)
    print("WC Prediction Ensemble")
    print("=" * 60)
    
    ensemble = get_ensemble()
    
    print("\n=== Predictions ===")
    tests = [
        ('Brazil', 'Croatia'), ('France', 'Morocco'),
        ('Argentina', 'Saudi Arabia'), ('England', 'Iran'),
        ('Germany', 'Japan'), ('Spain', 'Italy'),
        ('France', 'Brazil'), ('Argentina', 'France'),
    ]
    
    for home, away in tests:
        pred = ensemble.predict(home, away)
        wdl = pred['wdl']
        xg = pred['expected_goals']
        models = pred['models']
        
        print(f"\n{home} vs {away}")
        print(f"  Ensemble:  {wdl['home_win']:.1%} / {wdl['draw']:.1%} / {wdl['away_win']:.1%}  "
              f"xG: {xg['home']:.2f}-{xg['away']:.2f}")
        
        for name, m in models.items():
            mwdl = m['wdl']
            mxg = m['xg']
            print(f"  {name:15s}  {mwdl[0]:.1%} / {mwdl[1]:.1%} / {mwdl[2]:.1%}  "
                  f"xG: {mxg['home']:.2f}-{mxg['away']:.2f}")


