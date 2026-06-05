"""伤病/缺席检测引擎"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query
from data.tm_repo import get_club_squad

def get_team_injuries(team_name, league="E0"):
    """
    检测球队伤病/缺席情况
    通过 Transfermarkt 出场记录判断：最近N场比赛没上场的球员可能受伤

    Returns: {
        injured: [{name, position, overall, last_appearance, impact}],
        available: [{name, position, overall}],
        team_impact: float  # 对球队的影响系数
    }
    """
    from data.tm_repo import search_club
    from engine.player_ratings import get_club_squad_rated

    clubs = search_club(team_name, 3)
    if not clubs:
        return None

    squad = get_club_squad_rated(clubs[0]["club_id"])
    if not squad:
        return None

    injured = []
    available = []

    # Batch-query recent appearances for all top-22 players (1 query instead of 22)
    top22 = squad[:22]
    player_ids = []
    for p in top22:
        pid = int(p["id"].split(":")[1]) if ":" in p["id"] else None
        if pid:
            player_ids.append(pid)

    recent_by_player = {}
    if player_ids:
        placeholders = ",".join(["%s"] * len(player_ids))
        rows = query(f"""
            SELECT a.player_id, g.date, a.minutes_played
            FROM tm_appearances a
            JOIN tm_games g ON a.game_id = g.game_id
            WHERE a.player_id IN ({placeholders})
            ORDER BY g.date DESC
        """, player_ids, db="football_pred")
        for r in rows:
            pid = r["player_id"]
            if pid not in recent_by_player:
                recent_by_player[pid] = []
            if len(recent_by_player[pid]) < 5:
                recent_by_player[pid].append(r)

    for p in top22:
        pid = int(p["id"].split(":")[1]) if ":" in p["id"] else None
        if not pid:
            continue

        recent = recent_by_player.get(pid, [])
        last_played = recent[0]["date"] if recent else None

        appearances_in_last_5 = len([r for r in recent if r["minutes_played"] > 0]) if recent else 0

        if appearances_in_last_5 < 2 and p.get("overall", 0) >= 65:
            impact = p.get("overall", 50) / 100
            injured.append({
                "name": p["name"],
                "position": p["position"],
                "overall": p.get("overall", 0),
                "last_appearance": str(last_played) if last_played else "N/A",
                "recent_apps": appearances_in_last_5,
                "impact": round(impact, 2),
            })
        else:
            available.append({
                "name": p["name"],
                "position": p["position"],
                "overall": p.get("overall", 0),
            })

    # Compute team-level impact
    team_impact = 1.0
    for p in injured:
        pos = p["position"]
        if pos in ("Centre-Forward", "Attack"):
            team_impact -= 0.08 * p["impact"]
        elif pos in ("Central Midfield", "Attacking Midfield"):
            team_impact -= 0.05 * p["impact"]
        elif pos in ("Centre-Back", "Defender"):
            team_impact -= 0.04 * p["impact"]
        else:
            team_impact -= 0.03 * p["impact"]

    team_impact = max(team_impact, 0.7)

    # Confidence based on data coverage
    checked = len(squad[:22])
    if checked >= 18:
        confidence = "high"
    elif checked >= 10:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "injured": injured[:5],
        "available": available[:15],
        "team_impact": round(team_impact, 3),
        "total_checked": checked,
        "confidence": confidence,
        "note": "Injury detection is heuristic-based (appearance gaps). For production use, integrate a real injury data API.",
    }
