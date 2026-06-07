"""赔率 API — 赔率对比 + EV 扫描"""
from fastapi import APIRouter, Query, HTTPException
import sys, os, logging, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.match_repo import get_match_by_id, query
from engine.predictor import predict_match as do_predict


router = APIRouter()
logger = logging.getLogger(__name__)

def _api_error(message, exc, **context):
    """Log a failure with a stable id and raise HTTP 500."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception("%s error_id=%s context=%s", message, error_id, context, exc_info=exc)
    raise HTTPException(status_code=500, detail={
        "status": "error", "message": message, "error_id": error_id,
        "error_type": type(exc).__name__, "detail": str(exc),
    })


@router.get("/odds/compare")
def compare_odds(match_id: int = Query(..., description="比赛 ID")):
    """
    单场赔率对比：模型概率 vs 市场赔率 → EV
    """
    match = get_match_by_id(match_id)
    if not match:
        return {"status": "error", "message": f"Match {match_id} not found"}

    # 预测
    try:
        pred = do_predict(match["home_team"], match["away_team"], match["league_code"])
    except Exception as e:
        _api_error("Odds processing failed", e, match_id=match_id)

    # 计算 EV
    comparisons = []
    for outcome, prob_key, book_key in [
        ("home", "home_win", "avgh"),
        ("draw", "draw", "avgd"),
        ("away", "away_win", "avga"),
    ]:
        prob = pred[prob_key]
        odds_val = float(match.get(book_key, 0) or 0)
        if odds_val and prob > 0:
            fair = round(1 / prob, 2)
            ev = round(prob * odds_val - 1, 4)
            comparisons.append({
                "outcome": outcome,
                "model_prob": prob,
                "market_odds": odds_val,
                "fair_odds": fair,
                "ev": ev,
                "is_value": ev > 0,
            })

    return {
        "status": "ok",
        "match": f"{match['home_team']} vs {match['away_team']}",
        "league": match["league_code"],
        "predictions": pred,
        "comparisons": sorted(comparisons, key=lambda x: x["ev"], reverse=True),
    }


@router.get("/odds/scan")
def scan_ev(
    league: str = Query(default="E0", description="联赛代码"),
    min_ev: float = Query(default=0, description="最低 EV 阈值"),
):
    """
    扫描某联赛所有有赔率的比赛，返回 EV+ 列表
    """
    matches = query("""
        SELECT m.id, m.home_team, m.away_team, m.league_code,
               o.avgh, o.avgd, o.avga
        FROM matches m
        JOIN odds o ON m.id = o.match_id
        WHERE m.league_code = %s AND m.fthg IS NULL
        LIMIT 100
    """, [league])

    results = []
    for m in matches:
        try:
            pred = do_predict(m["home_team"], m["away_team"], m["league_code"])
        except Exception as e:
            logger.warning("Prediction failed for match %s vs %s: %s", m.get("home_team"), m.get("away_team"), e, exc_info=True)
            continue

        for outcome, prob_key, book_key in [
            ("home", "home_win", "avgh"),
            ("draw", "draw", "avgd"),
            ("away", "away_win", "avga"),
        ]:
            prob = pred[prob_key]
            odds_val = float(m.get(book_key, 0) or 0)
            if odds_val and prob > 0:
                ev = round(prob * odds_val - 1, 4)
                if ev >= min_ev:
                    results.append({
                        "match_id": m["id"],
                        "match": f"{m['home_team']} vs {m['away_team']}",
                        "outcome": outcome,
                        "model_prob": prob,
                        "market_odds": odds_val,
                        "fair_odds": round(1 / prob, 2),
                        "ev": ev,
                    })

    results.sort(key=lambda x: x["ev"], reverse=True)
    return {
        "status": "ok",
        "league": league,
        "scanned": len(matches),
        "ev_positive": len(results),
        "results": results[:30],
    }
