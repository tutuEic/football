# -*- coding: utf-8 -*-
"""
Stacking Ensemble — trains a meta-learner on base model predictions.
Uses logistic regression as meta-learner for interpretability.
"""
import sys, os, json
import numpy as np
from pathlib import Path
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
class StackingEnsemble:
    """
    Stacking ensemble that combines base model predictions.

    Layer 1: DC, Poisson Regression, XGBoost
    Layer 2: Logistic regression meta-learner
    """

    def __init__(self):
        self.meta_weights = None  # Shape: (n_models, 3) for H/D/A
        self.model_names = []
        self.fitted = False

    def _softmax(self, x):
        e = np.exp(x - np.max(x))
        return e / e.sum()

    def fit(self, base_predictions: dict, y_home: np.ndarray, y_away: np.ndarray):
        """
        Train meta-learner on base model predictions.

        Args:
            base_predictions: {model_name: (n_samples, 3) array of [P(H), P(D), P(A)]}
            y_home: home goals array
            y_away: away goals array
        """
        self.model_names = list(base_predictions.keys())
        n_models = len(self.model_names)
        n_samples = len(y_home)

        # Build labels
        y = np.zeros(n_samples, dtype=int)
        for i in range(n_samples):
            if y_home[i] > y_away[i]:
                y[i] = 0  # H
            elif y_home[i] == y_away[i]:
                y[i] = 1  # D
            else:
                y[i] = 2  # A

        # Stack base predictions: shape (n_samples, n_models * 3)
        X_meta = np.column_stack([base_predictions[m] for m in self.model_names])

        # One-hot encode labels
        y_onehot = np.zeros((n_samples, 3))
        for i in range(n_samples):
            y_onehot[i, y[i]] = 1

        # Train weights via optimization (minimize log-loss)
        def neg_log_loss(weights_flat):
            weights = weights_flat.reshape(n_models, 3)
            # Combine predictions
            final_probs = np.zeros((n_samples, 3))
            for c in range(3):
                for m_idx in range(n_models):
                    model_preds = base_predictions[self.model_names[m_idx]][:, c]
                    final_probs[:, c] += weights[m_idx, c] * model_preds

            # Normalize
            row_sums = final_probs.sum(axis=1, keepdims=True)
            row_sums = np.maximum(row_sums, 1e-10)
            final_probs = final_probs / row_sums

            # Log loss
            final_probs = np.maximum(final_probs, 1e-10)
            ll = -np.sum(y_onehot * np.log(final_probs))

            # L2 regularization
            reg = 0.001 * np.sum(weights_flat ** 2)
            return ll + reg

        # Initialize with equal weights
        x0 = np.ones(n_models * 3) / n_models

        # Bounds: weights between 0 and 1
        bounds = [(0, 1)] * (n_models * 3)

        result = minimize(neg_log_loss, x0, method='L-BFGS-B', bounds=bounds,
                         options={'maxiter': 2000})

        self.meta_weights = result.x.reshape(n_models, 3)
        self.fitted = True

        print(f"Stacking trained: {n_models} models")
        for i, name in enumerate(self.model_names):
            w = self.meta_weights[i]
            print(f"  {name}: H={w[0]:.3f} D={w[1]:.3f} A={w[2]:.3f}")

        return True

    def predict(self, base_predictions: dict) -> dict:
        """Generate ensemble prediction from base model outputs."""
        if not self.fitted:
            raise ValueError("Ensemble not fitted")

        final = np.zeros(3)
        for i, name in enumerate(self.model_names):
            if name in base_predictions:
                pred = base_predictions[name]
                for c in range(3):
                    final[c] += self.meta_weights[i, c] * pred[c]

        # Normalize
        total = max(final.sum(), 1e-10)
        final = final / total

        return {
            "home_win": round(float(final[0]), 4),
            "draw": round(float(final[1]), 4),
            "away_win": round(float(final[2]), 4),
        }

    def save(self, path):
        data = {
            "meta_weights": self.meta_weights.tolist(),
            "model_names": self.model_names,
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding='utf-8')

    def load(self, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        self.meta_weights = np.array(data["meta_weights"])
        self.model_names = data["model_names"]
        self.fitted = True
