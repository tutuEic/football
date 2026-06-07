# -*- coding: utf-8 -*-
"""
XGBoost model for football match outcome prediction.
Predicts P(H), P(D), P(A) directly as classification.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("Warning: xgboost not installed. Install with: pip install xgboost")

from features.feature_store import FEATURE_NAMES


class XGBoostPredictor:
    """XGBoost classifier for H/D/A prediction."""

    def __init__(self):
        self.model = None
        self.feature_names = FEATURE_NAMES
        self.fitted = False
        self.label_map = {0: "H", 1: "D", 2: "A"}
        self.label_reverse = {"H": 0, "D": 1, "A": 2}

    def _prepare_labels(self, home_goals, away_goals):
        """Convert goals to H/D/A labels."""
        labels = []
        for hg, ag in zip(home_goals, away_goals):
            if hg > ag:
                labels.append(0)  # H
            elif hg == ag:
                labels.append(1)  # D
            else:
                labels.append(2)  # A
        return np.array(labels)

    def fit(self, X, home_goals, away_goals, X_val=None, y_val_home=None, y_val_away=None):
        """Train XGBoost classifier."""
        if not HAS_XGB:
            raise RuntimeError("xgboost not installed")

        y = self._prepare_labels(
            np.array(home_goals) if not isinstance(home_goals, np.ndarray) else home_goals,
            np.array(away_goals) if not isinstance(away_goals, np.ndarray) else away_goals
        )

        # DMatrix
        dtrain = xgb.DMatrix(X, label=y, feature_names=self.feature_names)

        params = {
            "objective": "multi:softprob",
            "num_class": 3,
            "max_depth": 6,
            "eta": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "eval_metric": "mlogloss",
            "seed": 42,
            "verbosity": 0,
        }

        evals = [(dtrain, "train")]
        if X_val is not None:
            y_val = self._prepare_labels(
                np.array(y_val_home) if not isinstance(y_val_home, np.ndarray) else y_val_home,
                np.array(y_val_away) if not isinstance(y_val_away, np.ndarray) else y_val_away
            )
            dval = xgb.DMatrix(X_val, label=y_val, feature_names=self.feature_names)
            evals.append((dval, "val"))

        callbacks = [xgb.callback.EvaluationMonitor()]
        if X_val is not None:
            callbacks.append(xgb.callback.EarlyStopping(rounds=50, save_best=True))

        self.model = xgb.train(
            params, dtrain,
            num_boost_round=500,
            evals=evals,
            callbacks=callbacks,
            verbose_eval=False,
        )
        self.fitted = True
        print(f"XGBoost trained: {self.model.best_iteration} rounds, best_logloss={self.model.best_score:.4f}")
        return True

    def predict(self, features: dict) -> dict:
        """Predict match outcome."""
        if not self.fitted:
            raise ValueError("Model not fitted")

        x = np.array([[features.get(f, 0) for f in self.feature_names]])
        dtest = xgb.DMatrix(x, feature_names=self.feature_names)
        probs = self.model.predict(dtest)[0]

        return {
            "home_win": round(float(probs[0]), 4),
            "draw": round(float(probs[1]), 4),
            "away_win": round(float(probs[2]), 4),
            "model": "xgboost",
        }

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Predict batch of matches. Returns (n, 3) probability matrix."""
        dtest = xgb.DMatrix(X, feature_names=self.feature_names)
        return self.model.predict(dtest)

    def get_feature_importance(self) -> dict:
        """Get feature importance scores."""
        if not self.fitted:
            return {}
        importance = self.model.get_score(importance_type='gain')
        return dict(sorted(importance.items(), key=lambda x: -x[1]))

    def save(self, path):
        if self.model:
            self.model.save_model(str(path))

    def load(self, path):
        if not HAS_XGB:
            raise RuntimeError("xgboost not installed")
        self.model = xgb.Booster()
        self.model.load_model(str(path))
        self.fitted = True
