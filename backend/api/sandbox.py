"""沙盘模拟 API — 支持真实球员 ID 自动解析评分"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine.simulator import simulate
from engine.formations import list_formations
from engine.player_ratings import get_player_rating

router = APIRouter()


class PlayerSlot(BaseModel):
    name: str = "未知"
    position: str = "CM"
    player_id: Optional[int] = None       # Transfermarkt 球员 ID
    attack_rating: Optional[int] = None   # 手动覆盖
    defense_rating: Optional[int] = None
    att: Optional[dict] = None
    source: str = "custom"


class SquadConfig(BaseModel):
    formation: str = "4-3-3"
    players: List[PlayerSlot]


class SimulateRequest(BaseModel):
    team_a: SquadConfig
    team_b: SquadConfig
    simulations: int = Field(default=1000, ge=100, le=5000)
    home_advantage: bool = True
    match_context: str = "league"  # league, derby, title_decider, relegation, cup_ko, cup_final, cl_knockout, cl_final, friendly  # league, derby, title_decider, relegation, cup_ko, cup_final, cl_knockout, cl_final, friendly


def _resolve_player(p: PlayerSlot) -> dict:
    """将 PlayerSlot 解析为引擎可用的 dict，自动从 TM 获取评分"""
    d = p.model_dump()
    if p.player_id:
        rating = get_player_rating(p.player_id)
        if rating:
            d["name"] = rating["name"]
            d["position"] = rating["position"]
            d["attack_rating"] = p.attack_rating or rating.get("attack_rating")
            d["defense_rating"] = p.defense_rating or rating.get("defense_rating")
            d["att"] = p.att or rating.get("att")
            d["source"] = "transfermarkt"
    # Remove None-valued keys so engine falls back to defaults
    return {k: v for k, v in d.items() if v is not None}


@router.post("/sandbox/simulate")
def run_simulation(req: SimulateRequest):
    squad_a = {
        "formation": req.team_a.formation,
        "players": [_resolve_player(p) for p in req.team_a.players],
    }
    squad_b = {
        "formation": req.team_b.formation,
        "players": [_resolve_player(p) for p in req.team_b.players],
    }
    result = simulate(squad_a, squad_b, n=req.simulations, home_advantage=req.home_advantage, match_context=req.match_context)
    return {"status": "ok", **result}


@router.get("/sandbox/formations")
def get_formations():
    return {"formations": list_formations()}
