"""
Player ratings engine — FIFA-style 0-99 from Transfermarkt stats
With position categorization for Sandbox filtering
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.tm_repo import get_player_stats, get_player

POSITION_BASE = {
    "Goalkeeper":       {"attack": 15, "defense": 75, "pace": 55, "passing": 40, "physical": 70},
    "Centre-Back":      {"attack": 25, "defense": 82, "pace": 60, "passing": 55, "physical": 80},
    "Left-Back":        {"attack": 45, "defense": 72, "pace": 78, "passing": 65, "physical": 68},
    "Right-Back":       {"attack": 45, "defense": 72, "pace": 78, "passing": 65, "physical": 68},
    "Defensive Midfield":{"attack": 40, "defense": 75, "pace": 62, "passing": 72, "physical": 72},
    "Central Midfield": {"attack": 60, "defense": 60, "pace": 65, "passing": 78, "physical": 68},
    "Attacking Midfield":{"attack": 75, "defense": 35, "pace": 72, "passing": 82, "physical": 62},
    "Left Winger":      {"attack": 78, "defense": 25, "pace": 85, "passing": 75, "physical": 58},
    "Right Winger":     {"attack": 78, "defense": 25, "pace": 85, "passing": 75, "physical": 58},
    "Centre-Forward":   {"attack": 85, "defense": 20, "pace": 78, "passing": 65, "physical": 72},
    "Attack":           {"attack": 78, "defense": 25, "pace": 78, "passing": 68, "physical": 65},
    "Midfield":         {"attack": 55, "defense": 55, "pace": 66, "passing": 74, "physical": 66},
    "Defender":         {"attack": 35, "defense": 78, "pace": 68, "passing": 58, "physical": 75},
}

POSITION_CATEGORY = {
    "Goalkeeper": "GK",
    "Centre-Back": "DF", "Left-Back": "DF", "Right-Back": "DF",
    "Defender": "DF", "Sweeper": "DF", "Wing-Back": "DF",
    "Defensive Midfield": "MF", "Central Midfield": "MF",
    "Attacking Midfield": "MF", "Left Midfield": "MF", "Right Midfield": "MF",
    "Midfield": "MF",
    "Left Winger": "FW", "Right Winger": "FW",
    "Centre-Forward": "FW", "Second Striker": "FW", "Attack": "FW",
}

CATEGORY_SLOTS = {
    "GK": ["GK"],
    "DF": ["LB", "CB", "RB", "LWB", "RWB"],
    "MF": ["CM", "CDM", "CAM", "LM", "RM"],
    "FW": ["ST", "LW", "RW", "CF"],
}

def position_category(pos):
    if not pos: return "MF"
    # First check exact match in lookup table
    if pos in POSITION_CATEGORY:
        return POSITION_CATEGORY[pos]
    # Then pattern match (order matters!)
    p = pos.lower()
    if "goal" in p or "keeper" in p: return "GK"
    if "back" in p or "defend" in p or "sweeper" in p: return "DF"
    # "midfield" must be checked BEFORE "attack" (Attacking Midfield = MF, not FW)
    if "midfield" in p: return "MF"
    if "forward" in p or "winger" in p or "striker" in p or "attack" in p: return "FW"
    return "MF"


def get_player_rating(player_id):
    player = get_player(player_id)
    if not player: return None

    stats_rows = get_player_stats(player_id)
    stats = stats_rows[0] if stats_rows else {}

    pos = player.get("sub_position") or player.get("position") or "Midfield"
    base = POSITION_BASE.get(pos, POSITION_BASE["Midfield"])

    goals90 = float(stats.get("goals_per_90", 0) or 0)
    assists90 = float(stats.get("assists_per_90", 0) or 0)
    apps = int(stats.get("appearances", 0) or 0)
    market_val = int(player.get("market_value_in_eur", 0) or 0)

    shooting = min(round(base["attack"] + min(goals90 * 20, 15)), 99)
    passing = min(round(base["passing"] + min(assists90 * 12, 15)), 99)
    dribbling = min(round(base["attack"] - 5 + min(goals90 * 8, 10)), 99)
    defending = min(round(base["defense"]), 99)
    height = int(player.get("height_in_cm", 175) or 175)
    physical = min(round(base["physical"] + max((height - 175) * 0.3, -5)), 99)
    pace = min(round(base["pace"]), 99)

    attack_rating = round(shooting * 0.6 + dribbling * 0.3 + pace * 0.1)
    defense_rating = round(defending * 0.8 + physical * 0.2)
    raw_overall = (attack_rating + defense_rating) / 2

    if market_val > 0:
        mv_bonus = max(min(math.log10(max(market_val, 1)) * 2.0 - 10, 10), 0)
        raw_overall += mv_bonus

    overall = min(round(raw_overall), 99)
    cat = position_category(pos)

    return {
        "id": f"tm:{player_id}",
        "name": player.get("name", ""),
        "position": pos,
        "category": cat,
        "club": player.get("current_club_name", ""),
        "overall": overall,
        "attack_rating": attack_rating,
        "defense_rating": defense_rating,
        "att": {"pace": pace, "shooting": shooting, "passing": passing,
                "dribbling": dribbling, "defending": defending, "physical": physical},
        "market_value": f"EUR {market_val:,}" if market_val else "N/A",
        "goals_per_90": goals90, "assists_per_90": assists90, "appearances": apps,
        "source": "transfermarkt",
    }


def get_club_squad_rated(club_id, club_name=None):
    from data.tm_repo import get_club_squad, search_players as tm_search_players
    if club_id == 0 and club_name:
        # Fixtures-sourced club: search players by club name in TM data
        # Try multiple name variants (short name → full TM name mapping)
        players = []
        name_variants = [club_name]

        # Common abbreviation expansions
        name_map = {
            "man city": "manchester city",
            "man utd": "manchester united",
            "ath madrid": "atletico madrid",
            "ath bilbao": "athletic bilbao",
        }
        key = club_name.lower()
        if key in name_map:
            name_variants.append(name_map[key])

        # Also try individual words for partial matching
        words = [w for w in club_name.split() if len(w) >= 3]

        for variant in name_variants[:2]:  # Try short name + expanded name
            found = tm_search_players(variant, limit=60)
            for p in found:
                club = (p.get("current_club_name") or "").lower()
                # Check if the word matches the club name
                for w in words:
                    if w.lower() in club:
                        players.append(p)
                        break

        # Deduplicate
        seen = set()
        unique = []
        for p in players:
            if p["player_id"] not in seen:
                seen.add(p["player_id"])
                unique.append(p)
        players = unique[:40]
    else:
        players = get_club_squad(club_id)

    rated = []
    for p in players:
        r = get_player_rating(p["player_id"])
        if r:
            rated.append(r)
    rated.sort(key=lambda x: x["overall"], reverse=True)
    return rated


def search_players_rated(name, limit=10):
    from data.tm_repo import search_players
    players = search_players(name, limit)
    rated = []
    for p in players:
        r = get_player_rating(p["player_id"])
        if r: rated.append(r)
    return rated
