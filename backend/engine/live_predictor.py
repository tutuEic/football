# -*- coding: utf-8 -*-
"""
P2-1: In-Match Live Prediction
================================
Updates match predictions based on live match state:
- Current score
- Time remaining
- Red cards
- Momentum shifts

Uses Bayesian updating: prior = pre-match prediction, likelihood = current score + time.
"""
from scipy.stats import poisson


class LivePredictor:
    """
    In-match live prediction engine.
    
    Updates pre-match predictions based on:
    1. Current score (home_goals, away_goals)
    2. Time elapsed (minutes)
    3. Red cards (home_reds, away_reds)
    4. Pre-match expected goals (from DC model)
    """

    # Red card impact on expected goals (per red card)
    RED_CARD_ATTACK_PENALTY = 0.25   # 25% reduction in attack
    RED_CARD_DEFENCE_PENALTY = 0.15  # 15% increase in goals conceded
    
    # Time decay for remaining goals
    TIME_DECAY_RATE = 0.03  # Goals scored per minute decreases over time

    def __init__(self):
        pass

    def predict_live(self, pre_match_wdl, pre_match_xg, 
                     home_goals, away_goals, minutes_elapsed,
                     home_reds=0, away_reds=0):
        """
        Update match prediction based on live state.
        
        Args:
            pre_match_wdl: dict with home_win, draw, away_win (pre-match)
            pre_match_xg: dict with home, away (pre-match expected goals)
            home_goals: current home team goals
            away_goals: current away team goals
            minutes_elapsed: minutes played (0-90+)
            home_reds: number of red cards for home team
            away_reds: number of red cards for away team
            
        Returns:
            dict with updated predictions
        """
        minutes_remaining = max(90 - minutes_elapsed, 0)
        
        # Adjust expected goals for remaining time
        lam_h = pre_match_xg["home"]
        lam_a = pre_match_xg["away"]
        
        # Scale by remaining time (goals expected in remaining minutes)
        time_fraction = minutes_remaining / 90.0
        lam_h_remaining = lam_h * time_fraction
        lam_a_remaining = lam_a * time_fraction
        
        # Apply red card adjustments
        if home_reds > 0:
            lam_h_remaining *= (1 - self.RED_CARD_ATTACK_PENALTY * home_reds)
            lam_a_remaining *= (1 + self.RED_CARD_DEFENCE_PENALTY * home_reds)
        if away_reds > 0:
            lam_a_remaining *= (1 - self.RED_CARD_ATTACK_PENALTY * away_reds)
            lam_h_remaining *= (1 + self.RED_CARD_DEFENCE_PENALTY * away_reds)
        
        # Clamp to reasonable range
        lam_h_remaining = max(lam_h_remaining, 0.01)
        lam_a_remaining = max(lam_a_remaining, 0.01)
        
        # If match is effectively over (very few minutes remaining)
        if minutes_remaining <= 1:
            # Current score is almost certainly final
            if home_goals > away_goals:
                return self._make_result(
                    home_goals, away_goals, 0.95, 0.03, 0.02,
                    lam_h, lam_a, minutes_elapsed, home_reds, away_reds
                )
            elif away_goals > home_goals:
                return self._make_result(
                    home_goals, away_goals, 0.02, 0.03, 0.95,
                    lam_h, lam_a, minutes_elapsed, home_reds, away_reds
                )
            else:
                return self._make_result(
                    home_goals, away_goals, 0.02, 0.96, 0.02,
                    lam_h, lam_a, minutes_elapsed, home_reds, away_reds
                )
        
        # Compute probability of each additional goal combination
        # P(home scores k more goals) = Poisson(k, lam_h_remaining)
        # P(away scores k more goals) = Poisson(k, lam_a_remaining)
        
        max_additional = 5
        hw = 0.0
        dw = 0.0
        aw = 0.0
        
        for h_more in range(max_additional + 1):
            for a_more in range(max_additional + 1):
                p = (poisson.pmf(h_more, lam_h_remaining) * 
                     poisson.pmf(a_more, lam_a_remaining))
                
                final_h = home_goals + h_more
                final_a = away_goals + a_more
                
                if final_h > final_a:
                    hw += p
                elif final_h == final_a:
                    dw += p
                else:
                    aw += p
        
        # Normalize
        total = hw + dw + aw
        if total > 0:
            hw /= total
            dw /= total
            aw /= total

        # Bayesian blend: weight pre-match prior more early, Poisson model more late
        if pre_match_wdl:
            blend = max(0.05, minutes_remaining / 90.0)  # prior fades as match progresses
            hw = pre_match_wdl.get("home_win", hw) * blend + hw * (1 - blend)
            dw = pre_match_wdl.get("draw", dw) * blend + dw * (1 - blend)
            aw = pre_match_wdl.get("away_win", aw) * blend + aw * (1 - blend)
            # Re-normalize
            s = hw + dw + aw
            if s > 0:
                hw /= s; dw /= s; aw /= s
        
        return self._make_result(
            home_goals, away_goals, hw, dw, aw,
            lam_h, lam_a, minutes_elapsed, home_reds, away_reds
        )

    def _make_result(self, home_goals, away_goals, hw, dw, aw,
                     pre_lam_h, pre_lam_a, minutes, home_reds, away_reds):
        """Build result dict."""
        # Most likely final score
        # Simple: current score + 1 more goal for stronger side
        if hw > dw and hw > aw:
            likely_h = home_goals + (1 if minutes < 80 else 0)
            likely_a = away_goals
        elif aw > dw and aw > hw:
            likely_h = home_goals
            likely_a = away_goals + (1 if minutes < 80 else 0)
        else:
            likely_h = home_goals
            likely_a = away_goals
        
        return {
            "home_win": round(hw, 4),
            "draw": round(dw, 4),
            "away_win": round(aw, 4),
            "current_score": str(home_goals) + "-" + str(away_goals),
            "minutes_elapsed": minutes,
            "minutes_remaining": max(90 - minutes, 0),
            "home_reds": home_reds,
            "away_reds": away_reds,
            "pre_match_xg": {"home": round(pre_lam_h, 2), "away": round(pre_lam_a, 2)},
            "xg_remaining": {"home": round(pre_lam_h * max(90-minutes, 0)/90, 2), 
                             "away": round(pre_lam_a * max(90-minutes, 0)/90, 2)},
            "most_likely_final": str(likely_h) + "-" + str(likely_a),
            "model": "live_v1",
        }
