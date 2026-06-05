"""
Team strength calculator.
Input: 11 players + formation -> Output: (attack_strength, defense_strength)

Core formulas:
  attack_strength  = sum(player_attack * position_attack_weight) / 100 * formation_attack_bonus
  defense_strength = sum(player_defense * position_defense_weight) / 100 * formation_defense_bonus

Attack rating (default):  shooting*0.45 + dribbling*0.25 + passing*0.20 + pace*0.05 + physical*0.05
Defense rating (default): defending*0.65 + physical*0.20 + passing*0.10 + dribbling*0.05

Passing contributes to attack (creative play) and defense (interceptions/pressing).
Physical contributes to both (strength in duels, hold-up play).
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
    Returns (attack_strength, defense_strength) in log-space.
    """
    formation = get_formation(squad.get("formation", "4-4-2"))
    weights = formation["position_weights"]
    positions = formation["positions"]
    players = squad.get("players", [])

    total_attack = 0.0
    total_defense = 0.0

    for i, player in enumerate(players):
        actual_pos = player.get("position", positions[i] if i < len(positions) else "CM")
        w = weights.get(actual_pos, {"attack": 0.5, "defense": 0.5})

        att = player.get("att") or {}
        if player.get("attack_rating") is not None:
            att_val = player["attack_rating"]
        else:
            att_val = (
                att.get("shooting", 50) * 0.45 +
                att.get("dribbling", 50) * 0.25 +
                att.get("passing", 50) * 0.20 +
                att.get("pace", 50) * 0.05 +
                att.get("physical", 50) * 0.05
            )

        if player.get("defense_rating") is not None:
            def_val = player["defense_rating"]
        else:
            def_val = (
                att.get("defending", 50) * 0.65 +
                att.get("physical", 50) * 0.20 +
                att.get("passing", 50) * 0.10 +
                att.get("dribbling", 50) * 0.05
            )

        total_attack += att_val * w["attack"] / 100
        total_defense += def_val * w["defense"] / 100

    total_attack *= formation["attack_bonus"]
    total_defense *= formation["defense_bonus"]

    return round(total_attack, 4), round(total_defense, 4)


def squad_summary(squad: dict) -> dict:
    """Generate team summary."""
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
