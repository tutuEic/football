"""
球队强度计算器
输入: 11 个球员 + 阵型 → 输出: (attack_strength, defense_strength)

核心公式:
  attack_strength  = Σ (球员攻击值 × 位置攻击权重) / 100 × 阵型攻击加成
  defense_strength = Σ (球员防守值 × 位置防守权重) / 100 × 阵型防守加成

返回的对数值用于 Dixon-Coles: λ = exp(attack_home - defense_away + γ)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from formations import get_formation, get_positions

def calc_team_strength(squad: dict) -> tuple:
    """
    squad = {
        formation: "4-3-3",
        players: [{name, position, attack_rating, defense_rating, att:{...}}, ...]
    }
    返回 (attack_strength, defense_strength) — 对数空间
    """
    formation = get_formation(squad.get("formation", "4-4-2"))
    weights = formation["position_weights"]
    positions = formation["positions"]
    players = squad.get("players", [])

    total_attack = 0.0
    total_defense = 0.0

    for i, player in enumerate(players):
        # 确定该位置的实际角色
        actual_pos = player.get("position", positions[i] if i < len(positions) else "CM")
        w = weights.get(actual_pos, {"attack": 0.5, "defense": 0.5})

        # 获取球员属性
        att = player.get("att") or {}
        if player.get("attack_rating") is not None:
            att_val = player["attack_rating"]
        else:
            att_val = (
                att.get("shooting", 50) * 0.6 +
                att.get("dribbling", 50) * 0.3 +
                att.get("pace", 50) * 0.1
            )

        if player.get("defense_rating") is not None:
            def_val = player["defense_rating"]
        else:
            def_val = (
                att.get("defending", 50) * 0.8 +
                att.get("physical", 50) * 0.2
            )

        total_attack += att_val * w["attack"] / 100
        total_defense += def_val * w["defense"] / 100

    # 阵型全局加成
    total_attack *= formation["attack_bonus"]
    total_defense *= formation["defense_bonus"]

    return round(total_attack, 4), round(total_defense, 4)


def squad_summary(squad: dict) -> dict:
    """生成球队摘要信息"""
    att, deff = calc_team_strength(squad)
    formation = get_formation(squad.get("formation", "4-4-2"))
    players = squad.get("players", [])

    avg_attack = sum(
        (p.get("attack_rating") or 50) for p in players
    ) / max(len(players), 1)
    avg_defense = sum(
        (p.get("defense_rating") or 50) for p in players
    ) / max(len(players), 1)

    return {
        "formation": formation["name"],
        "formation_label": formation["label"],
        "attack_strength": att,
        "defense_strength": deff,
        "avg_player_attack": round(avg_attack, 1),
        "avg_player_defense": round(avg_defense, 1),
        "player_count": len(players),
    }
