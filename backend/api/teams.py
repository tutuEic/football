"""球队 API — 阵容 / 统计 / 对比"""
from fastapi import APIRouter, Query
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.match_repo import get_team_names
from engine.predictor import load_model
from engine.player_ratings import get_club_squad_rated
from data.tm_repo import search_club

router = APIRouter()


@router.get("/teams")
def list_teams(league: str = Query(default="E0")):
    """某联赛的球队列表"""
    teams = get_team_names(league)
    return {"league": league, "teams": [t["name"] for t in teams]}


@router.get("/teams/{team_name}/stats")
def team_stats(team_name: str, league: str = Query(default="E0")):
    """球队攻防强度 + 从 Transfermarkt 匹配阵容"""
    result = {"team": team_name, "league": league}

    # DC 模型攻防强度
    try:
        model = load_model(league)
        strength = model.get_team_strength(team_name)
        if strength:
            result["attack"] = round(strength["attack"], 3)
            result["defence"] = round(strength["defence"], 3)
    except Exception:
        result["attack"] = None
        result["defence"] = None

    # 匹配 Transfermarkt 俱乐部
    clubs = search_club(team_name, 3)
    if clubs:
        best = clubs[0]
        result["tm_club_id"] = best["club_id"]
        result["tm_club_name"] = best["name"]
        result["squad_size"] = best.get("squad_size")
        result["total_market_value"] = best.get("total_market_value")
        result["coach"] = best.get("coach_name")
        result["stadium"] = best.get("stadium_name")

        # 获取阵容
        squad = get_club_squad_rated(best["club_id"])
        result["squad"] = squad[:22]  # 前22人

    return result
