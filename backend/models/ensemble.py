# -*- coding: utf-8 -*-
"""
Ensemble Model — combines predictions from multiple models.
# Uses simple weighted averaging (can be upgraded to stacking).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EnsemblePredictor:
    """Combines predictions from DC, Poisson Regression, and optionally XGBoost."""

    def __init__(self):
        self.models = {}
        self.weights = {
            "dixon_coles": 0.50,
            "poisson_regression": 0.35,
            "xgboost": 0.15,
        }

    def register_model(self, name: str, model):
        self.models[name] = model

    def predict(self, home_team: str, away_team: str, league: str,
                features: dict = None) -> dict:
        """
        # Generate ensemble prediction.

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League code
            features: Pre-computed feature dict (optional)
        """
        predictions = {}
        weights_used = {}

        # Dixon-Coles prediction
        if "dixon_coles" in self.models:
            try:
                from engine.predictor import predict_match
                dc_pred = predict_match(home_team, away_team, league)
                predictions["dixon_coles"] = {
                    "home_win": dc_pred["home_win"],
                    "draw": dc_pred["draw"],
                    "away_win": dc_pred["away_win"],
                    "xg_home": dc_pred["exp_home_goals"],
                    "xg_away": dc_pred["exp_away_goals"],
                }
                weights_used["dixon_coles"] = self.weights["dixon_coles"]
            except Exception as e:
                print(f"DC model failed: {e}")

        # Poisson Regression prediction
        if "poisson_regression" in self.models and features:
            try:
                pr_pred = self.models["poisson_regression"].predict(features)
                predictions["poisson_regression"] = {
                    "home_win": pr_pred["home_win"],
                    "draw": pr_pred["draw"],
                    "away_win": pr_pred["away_win"],
                    "xg_home": pr_pred["expected_goals"]["home"],
                    "xg_away": pr_pred["expected_goals"]["away"],
                }
                weights_used["poisson_regression"] = self.weights["poisson_regression"]
            except Exception as e:
                print(f"Poisson regression failed: {e}")

        if not predictions:
            raise ValueError("No models available for prediction")

        # Normalize weights
        total_weight = sum(weights_used.values())
        for k in weights_used:
            weights_used[k] /= total_weight

        # Weighted average
        final = {"home_win": 0, "draw": 0, "away_win": 0, "xg_home": 0, "xg_away": 0}
        for model_name, pred in predictions.items():
            w = weights_used[model_name]
            for key in final:
                final[key] += pred.get(key, 0) * w

        # Round
        for key in ["home_win", "draw", "away_win"]:
            final[key] = round(final[key], 4)
        final["xg_home"] = round(final["xg_home"], 2)
        final["xg_away"] = round(final["xg_away"], 2)

        # Determine most likely outcome
        outcomes = {"H": final["home_win"], "D": final["draw"], "A": final["away_win"]}
        final["predicted"] = max(outcomes, key=outcomes.get)
        final["confidence"] = "high" if max(outcomes.values()) > 0.55 else (
            "medium" if max(outcomes.values()) > 0.40 else "low"
        )

        #  Include individual model predictions for transparency
        final["model_predictions"] = {
            k: {key: round(v, 4) if isinstance(v, float) else v
                for key, v in pred.items()}
            for k, pred in predictions.items()
        }
        final["weights_used"] = {k: round(v, 3) for k, v in weights_used.items()}
        final["models_used"] = list(predictions.keys())

        return final
