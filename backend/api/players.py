"""球员 API — 搜索 / 创建自定义球员"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.sofifa_client import search_player as sofifa_search
from data.mysql_client import query, execute
from engine.player_ratings import search_players_rated, get_player_rating

router = APIRouter()


class CustomPlayerRequest(BaseModel):
    name: str
    position: str = "CM"
    pace: int = 50; shooting: int = 50; passing: int = 50
    dribbling: int = 50; defending: int = 50; physical: int = 50


@router.get("/players/search")
def search_player(q: str = Query(...), limit: int = 20):
    """搜索球员（含评分）"""
    results = search_players_rated(q, limit)
    return {"status": "ok", "query": q, "count": len(results), "players": results}


@router.get("/players/{player_id}")
def player_detail(player_id: int):
    """球员详情 + 评分 + 赛季统计"""
    rating = get_player_rating(player_id)
    if not rating:
        return {"status": "error", "message": f"Player {player_id} not found"}
    from data.tm_repo import get_player_stats, get_player_recent_games
    return {"status": "ok", 
        "rating": rating,
        "stats": get_player_stats(player_id),
        "recent_games": get_player_recent_games(player_id, 10),
    }


@router.get("/players/{player_id}/rating")
def player_rating_only(player_id: int):
    """仅返回球员评分卡"""
    rating = get_player_rating(player_id)
    if not rating:
        return {"status": "error", "message": f"Player {player_id} not found"}
    return rating


@router.post("/players/custom")
def create_custom_player(req: CustomPlayerRequest):
    """创建自定义球员"""
    attack_rating = round(req.shooting * 0.6 + req.dribbling * 0.3 + req.pace * 0.1)
    defense_rating = round(req.defending * 0.8 + req.physical * 0.2)
    overall = round((attack_rating + defense_rating) / 2)
    pid = execute(
        """INSERT INTO custom_players (name, source, position, pace, shooting, passing,
           dribbling, defending, physical, attack_rating, defense_rating, overall)
           VALUES (%s,'custom',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        [req.name, req.position, req.pace, req.shooting, req.passing,
         req.dribbling, req.defending, req.physical, attack_rating, defense_rating, overall],
        db="football_pred")
    return {"status": "created", "id": pid, "name": req.name, "overall": overall}


@router.get("/players/custom")
def list_custom_players():
    """列出所有自定义球员"""
    return query("SELECT * FROM custom_players ORDER BY created_at DESC", db="football_pred")
