# -*- coding: utf-8 -*-
"""
Fixtures API - ???? + ?? + ??
=====================================
??????????????????????? EV?
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
import sys, os, logging, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query

router = APIRouter()
logger = logging.getLogger(__name__)

def _api_error(message, exc, **context):
    """Log a failure with a stable id and return a client-safe error."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception("%s error_id=%s context=%s", message, error_id, context, exc_info=exc)
    return {"status": "error", "message": message, "error_id": error_id,
            "error_type": type(exc).__name__, "detail": str(exc)}


def _get_prediction(home_team, away_team, league):
    """Predict a fixture using the appropriate model for the league."""
    try:
        if league == "WC2026":
            from engine.wc_predictor import predict_wc_match
            pred = predict_wc_match(home_team, away_team, {
                "stage": "group", "matchday": 1,
                "is_host": False, "in_host_country": True,
            })
            wdl = pred["wdl"]
            eg = pred["expected_goals"]
            return {
                "home_win": wdl["home_win"],
                "draw": wdl["draw"],
                "away_win": wdl["away_win"],
                "exp_home_goals": eg["home"],
                "exp_away_goals": eg["away"],
                "model": "wc_predictor",
            }
        elif league == "CL":
            from api.predict import _cl_predict
            return _cl_predict(home_team, away_team)
        else:
            from engine.full_predictor import get_ensemble_wdl
            ens = get_ensemble_wdl(home_team, away_team, league)
            return {
                "home_win": ens["home_win"],
                "draw": ens["draw"],
                "away_win": ens["away_win"],
                "exp_home_goals": ens.get("xg_home", 1.3),
                "exp_away_goals": ens.get("xg_away", 1.1),
                "model": "ensemble",
                "models_used": ens.get("models_used", []),
            }
    except Exception as e:
        logger.warning(
            "Fixture prediction failed for %s vs %s [%s]: %s",
            home_team, away_team, league, e, exc_info=True,
        )
        return None


def _calc_fair_odds(prob):
    """?? -> ???"""
    if prob and prob > 0:
        return round(1 / prob, 2)
    return None


def _calc_ev(prob, market_odds):
    """????? EV"""
    if prob and market_odds and market_odds > 0:
        return round(prob * market_odds - 1, 4)
    return None


@router.get("/fixtures/predictions")
def upcoming_with_predictions(
    league: Optional[str] = Query(None, description="??????=??"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    ?????? + ?? + ???? + EV?
    ??????????????
    """
    where = "WHERE (f.status IS NULL OR f.status != 'finished')"
    params = []
    if league:
        where += " AND f.league_code=%s"
        params.append(league)

    rows = query(f"""
        SELECT f.id, f.league_code, f.match_date, f.match_time,
               f.home_team, f.away_team,
               f.odds_home, f.odds_draw, f.odds_away,
               f.status
        FROM fixtures f
        {where}
        ORDER BY f.match_date ASC, f.match_time ASC
        LIMIT %s
    """, params + [limit], db="football_pred")

    results = []
    for r in rows:
        item = {
            "fixture_id": r["id"],
            "league": r["league_code"],
            "date": str(r["match_date"]),
            "time": r["match_time"],
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "status": r["status"] or "scheduled",
        }

        # ????
        market_h = float(r["odds_home"]) if r["odds_home"] else None
        market_d = float(r["odds_draw"]) if r["odds_draw"] else None
        market_a = float(r["odds_away"]) if r["odds_away"] else None
        item["market_odds"] = {
            "home": market_h, "draw": market_d, "away": market_a
        }

        # ??
        pred = _get_prediction(r["home_team"], r["away_team"], r["league_code"])
        if pred:
            hp, dp, ap = pred["home_win"], pred["draw"], pred["away_win"]
            item["prediction"] = {
                "home_win": hp, "draw": dp, "away_win": ap,
                "xg_home": pred.get("exp_home_goals"),
                "xg_away": pred.get("exp_away_goals"),
                "model": pred.get("model", "unknown"),
            }

            # ???? (???????)
            item["fair_odds"] = {
                "home": _calc_fair_odds(hp),
                "draw": _calc_fair_odds(dp),
                "away": _calc_fair_odds(ap),
            }

            # EV (???????)
            item["ev"] = {
                "home": _calc_ev(hp, market_h),
                "draw": _calc_ev(dp, market_d),
                "away": _calc_ev(ap, market_a),
            }

            # ????
            best_ev = None
            best_outcome = None
            for outcome, ev_val in item["ev"].items():
                if ev_val is not None and (best_ev is None or ev_val > best_ev):
                    best_ev = ev_val
                    best_outcome = outcome
            item["best_value"] = {
                "outcome": best_outcome,
                "ev": best_ev,
                "is_value": best_ev is not None and best_ev > 0,
            } if best_ev is not None else None

            # ???
            max_p = max(hp, dp, ap)
            gap = max_p - sorted([hp, dp, ap], reverse=True)[1]
            item["confidence"] = "high" if gap > 0.30 else ("medium" if gap > 0.15 else "low")

        results.append(item)

    return {"fixtures": results, "count": len(results)}


class OddsUpdate(BaseModel):
    fixture_id: int
    odds_home: float
    odds_draw: float
    odds_away: float


@router.post("/fixtures/update-odds")
def update_fixture_odds(req: OddsUpdate):
    """Update odds for a fixture."""
    from data.mysql_client import execute
    affected = execute(
        "UPDATE fixtures SET odds_home=%s, odds_draw=%s, odds_away=%s WHERE id=%s",
        [req.odds_home, req.odds_draw, req.odds_away, req.fixture_id],
        db="football_pred"
    )
    return {"status": "ok", "updated": affected or 0}
