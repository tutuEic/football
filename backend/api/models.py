"""模型管理 API"""
from fastapi import APIRouter, Query
import sys, os, logging, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine.predictor import list_available_models
from engine.trainer import train_league
from engine.backtest import backtest, run_league_backtests, betting_backtest, compare_model_versions

router = APIRouter()
logger = logging.getLogger(__name__)

def _api_error(message, exc, **context):
    """Log a failure with a stable id and return a client-safe error."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception("%s error_id=%s context=%s", message, error_id, context, exc_info=exc)
    return {"status": "error", "message": message, "error_id": error_id,
            "error_type": type(exc).__name__, "detail": str(exc)}


@router.get("/models")
def list_models():
    """列出所有已训练的模型"""
    return list_available_models()


@router.get("/models/ensemble")
def list_ensemble_leagues():
    """列出所有有完整集成模型的联赛 (Poisson + XGBoost + Stacking)"""
    from pathlib import Path
    # Resolve models dir relative to this file (backend/api/models.py -> backend/models)
    _this_dir = Path(__file__).resolve().parent
    model_dir = _this_dir.parent / "models"
    if not model_dir.exists():
        # Fallback: try from cwd
        model_dir = Path.cwd() / "backend" / "models"
    
    leagues = {}
    for f in model_dir.glob("stacking_*.json"):
        code = f.stem.replace("stacking_", "")
        has_poisson = (model_dir / f"poisson_{code}.json").exists()
        has_xgboost = (model_dir / f"xgboost_{code}.json").exists()
        has_dc = any(model_dir.glob(f"dc_{code}_*.json"))
        
        if has_poisson and has_xgboost:
            leagues[code] = {
                "poisson": has_poisson,
                "xgboost": has_xgboost,
                "stacking": True,
                "dc": has_dc,
            }
    
    return {"status": "ok", "count": len(leagues), "leagues": leagues}


@router.post("/models/train")
def train_model(league: str = "E0"):
    """触发模型训练"""
    try:
        model, path = train_league(league)
        return {
            "status": "ok",
            "league": league,
            "file": path,
            "teams": len(model.teams),
            "rho": round(model.params["rho"], 4),
            "gamma": round(model.params["gamma"], 4),
        }
    except Exception as e:
        return _api_error("Model training failed", e, league=league)


@router.post("/models/backtest")
def run_backtest(league: str = "E0", season: str = None):
    """
    回测某联赛

    - 不指定 season: 对所有可用赛季回测，返回到平均指标
    - 指定 season: 只测该赛季
    """
    if season:
        r = backtest(league, season)
        return r
    else:
        results = run_league_backtests(league)
        if results:
            accs = [r["accuracy"] for r in results if "accuracy" in r]
            briers = [r["brier_score"] for r in results if "brier_score" in r]
            return {
                "league": league,
                "avg_accuracy": round(sum(accs) / len(accs), 3) if accs else None,
                "avg_brier": round(sum(briers) / len(briers), 3) if briers else None,
                "per_season": results,
            }
        return {"error": "No results"}


@router.post("/models/betting-backtest")
def run_betting_backtest(
    league: str = "E0",
    season: str = Query(default=None),
    min_ev: float = Query(default=0.0),
    stake: float = Query(default=1.0),
):
    """Betting ROI backtest: simulates flat-stake bets when model EV > threshold."""
    if not season:
        from data.match_repo import get_seasons
        seasons = get_seasons(league)
        season = seasons[-1] if seasons else "2526"
    try:
        return betting_backtest(league, season, min_ev=min_ev, stake=stake)
    except Exception as e:
        return _api_error("Betting backtest failed", e, league=league, season=season)


@router.post("/models/compare-versions")
def compare_dc_versions(
    league: str = "E0",
    season: str = Query(default=None),
    min_ev: float = Query(default=0.0),
):
    """Compare standard DC vs time-weighted DC model accuracy and betting ROI."""
    if not season:
        from data.match_repo import get_seasons
        seasons = get_seasons(league)
        season = seasons[-1] if seasons else "2526"
    try:
        return compare_model_versions(league, season, min_ev=min_ev)
    except Exception as e:
        return _api_error("Compare versions failed", e, league=league, season=season)


@router.get("/models/compare")
def compare_models():
    """对比多个联赛的回测表现"""
    from engine.backtest import compare_leagues
    return compare_leagues()

