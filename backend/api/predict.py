# -*- coding: utf-8 -*-
"""Prediction API v3 with caching and confidence scores."""
from fastapi import APIRouter, Query
from pydantic import BaseModel
import sys, os, time, hashlib, json, logging, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine.predictor import predict_match as dc_predict, calibrate_wdl
from engine.full_predictor import full_prediction_v3

logger = logging.getLogger(__name__)
# CL ????? (????????)
def _cl_predict(home_team, away_team):
    """?? Elo + ???????"""
    from features.elo import get_elo_rating
    from data.tm_repo import search_club
    from data.mysql_client import query
    import math
    
    elo_h = get_elo_rating(home_team)
    elo_a = get_elo_rating(away_team)
    
    # ????
    def get_market_value(team_name):
        try:
            clubs = search_club(team_name)
            if clubs:
                return int(clubs[0].get("total_market_value", 0) or 0)
        except:
            pass
        return 0
    
    mv_h = get_market_value(home_team)
    mv_a = get_market_value(away_team)
    
    # ??? Elo ?? (log scale)
    mv_bonus_h = math.log10(max(mv_h, 1e6)) * 10 - 60 if mv_h > 0 else 0
    mv_bonus_a = math.log10(max(mv_a, 1e6)) * 10 - 60 if mv_a > 0 else 0
    
    # ????
    total_h = elo_h + mv_bonus_h + 30  # ????
    total_a = elo_a + mv_bonus_a
    
    diff = total_h - total_a
    
    # Elo ? -> ?? (logistic)
    home_win = 1 / (1 + 10 ** (-diff / 400))
    away_win = 1 / (1 + 10 ** (diff / 400))
    draw = max(0.15, 1 - home_win - away_win)
    
    # ???
    total = home_win + draw + away_win
    home_win /= total
    draw /= total
    away_win /= total
    
    # ????
    xg_h = max(0.5, 1.3 + diff / 800)
    xg_a = max(0.5, 1.1 - diff / 800)
    
    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "exp_home_goals": round(xg_h, 2),
        "exp_away_goals": round(xg_a, 2),
        "model": "elo_cross_league",
    }



router = APIRouter()

# Simple in-memory cache (TTL=5min)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 300  # seconds


def _cache_key(*args):
    raw = json.dumps(args, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str):
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: dict):
    _cache[key] = (time.time(), data)
    # Evict old entries if cache grows large
    if len(_cache) > 500:
        cutoff = time.time() - CACHE_TTL
        stale = [k for k, (ts, _) in _cache.items() if ts < cutoff]
        for k in stale:
            del _cache[k]


def _prediction_error(message: str, exc: Exception, **context) -> dict:
    """Log a prediction failure with a stable id and return a client-safe error."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception(
        "%s error_id=%s context=%s",
        message,
        error_id,
        context,
        exc_info=exc,
    )
    return {
        "status": "error",
        "message": message,
        "error_id": error_id,
        "error_type": type(exc).__name__,
        "detail": str(exc),
    }


class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    league: str = "E0"


def _compute_confidence(result: dict) -> str:
    """Estimate prediction confidence from probability distribution."""
    probs = [result.get("home_win", 0), result.get("draw", 0), result.get("away_win", 0)]
    max_p = max(probs)
    second_p = sorted(probs, reverse=True)[1]
    gap = max_p - second_p
    if gap > 0.30:
        return "high"
    elif gap > 0.15:
        return "medium"
    else:
        return "low"


@router.post("/predict")
def predict(req: PredictRequest):
    """Quick prediction (DC formula)."""
    key = _cache_key("predict", req.home_team, req.away_team, req.league)
    cached = _get_cached(key)
    if cached:
        return cached
    try:
        # Try ensemble first
        try:
            # CL ???????
            if req.league == "CL":
                result = _cl_predict(req.home_team, req.away_team)
            else:
                from engine.full_predictor import get_ensemble_wdl
                ens = get_ensemble_wdl(req.home_team, req.away_team, req.league)
                result = {
                    "home_win": ens["home_win"],
                    "draw": ens["draw"],
                    "away_win": ens["away_win"],
                    "exp_home_goals": ens.get("xg_home", 1.3),
                    "exp_away_goals": ens.get("xg_away", 1.1),
                    "model": "ensemble",
                    "models_used": ens.get("models_used", []),
                    "weights": ens.get("weights", {}),
                }
        except Exception as e:
            logger.warning(
                "Ensemble prediction failed; falling back to Dixon-Coles. "
                "home=%s away=%s league=%s error=%s",
                req.home_team,
                req.away_team,
                req.league,
                e,
                exc_info=True,
            )
            result = dc_predict(req.home_team, req.away_team, req.league)
        # Apply probability calibration
        result["raw_home_win"] = result["home_win"]
        result["raw_draw"] = result["draw"]
        result["raw_away_win"] = result["away_win"]
        calibrate_wdl(result)
        result["confidence"] = _compute_confidence(result)
        response = {"status": "ok", **result}
        _set_cached(key, response)
        return response
    except Exception as e:
        return _prediction_error(
            "Prediction failed",
            e,
            endpoint="/predict",
            home_team=req.home_team,
            away_team=req.away_team,
            league=req.league,
        )


@router.post("/predict/full")
def predict_full(req: PredictRequest, simulations: int = Query(default=2000, ge=100, le=10000)):
    """
    Full prediction v3 with Monte Carlo simulation.
    Returns: W/D/L%, score distribution, over/under, key players, injuries, factors.
    """
    key = _cache_key("predict_full", req.home_team, req.away_team, req.league, simulations)
    cached = _get_cached(key)
    if cached:
        return cached
    try:
        result = full_prediction_v3(req.home_team, req.away_team, req.league, simulations)
        # Apply probability calibration to WDL
        wdl = result.get("wdl", {})
        result["raw_wdl"] = {"home_win": wdl.get("home_win", 0), "draw": wdl.get("draw", 0), "away_win": wdl.get("away_win", 0)}
        calibrate_wdl(wdl)
        result["confidence"] = _compute_confidence(result.get("wdl", {}))
        # Append historical odds context
        try:
            from engine.odds_history import find_similar_odds_matches
            odds_hist = find_similar_odds_matches(req.home_team, req.away_team, req.league)
            if odds_hist:
                result["odds_history"] = odds_hist
        except Exception as e:
            logger.warning(
                "Odds history lookup failed. home=%s away=%s league=%s error=%s",
                req.home_team,
                req.away_team,
                req.league,
                e,
                exc_info=True,
            )
        response = {"status": "ok", **result}
        _set_cached(key, response)
        return response
    except Exception as e:
        return _prediction_error(
            "Full prediction failed",
            e,
            endpoint="/predict/full",
            home_team=req.home_team,
            away_team=req.away_team,
            league=req.league,
            simulations=simulations,
        )



@router.get("/predict/calibration")
def get_calibration():
    """Return the probability calibration curve computed from historical data."""
    from engine.predictor import get_calibration_info
    return get_calibration_info()
