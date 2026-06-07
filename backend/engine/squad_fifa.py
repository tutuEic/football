"""
FIFA20-based squad builder 鈥?real player names + ratings for ALL leagues
# Falls back to fixture-based estimator when no FIFA data exists for a team
"""
import csv, os, sys, random
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FIFA_PATH

# Load FIFA20 data
_fifa_cache = None

def _load_fifa():
    global _fifa_cache
    if _fifa_cache is not None:
        return _fifa_cache
    
    _fifa_cache = defaultdict(list)
    if not os.path.exists(FIFA_PATH):
        print(f"FIFA data not found at {FIFA_PATH}")
        return _fifa_cache
    
    with open(FIFA_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            club = (row.get("CLUB") or "").strip()
            if club:
                _fifa_cache[club.lower()].append(row)
    
    print(f"Loaded FIFA20: {sum(len(v) for v in _fifa_cache.values())} players from {len(_fifa_cache)} clubs")
    return _fifa_cache


def _fifa_to_player(row, club_name, idx):
    """Convert FIFA20 row to player dict"""
    try:
        rating = int(row.get("RATING", 65) or 65)
    except Exception:
        rating = 65
    
    pos = row.get("POSITION", "CM").strip()
    cat = _pos_to_category(pos)
    
    # Map FIFA attrs to our format
    try:
        pace = int(row.get("PACE", 65) or 65)
        shooting = int(row.get("SHOOTING", 50) or 50)
        passing = int(row.get("PASSING", 60) or 60)
        dribbling = int(row.get("DRIBBLING", 60) or 60)
        defending = int(row.get("DEFENDING", 45) or 45)
        physical = int(row.get("PHYSICAL", 60) or 60)
    except Exception:
        pace = shooting = passing = dribbling = defending = physical = 65
    
    attack_rating = round(shooting * 0.6 + dribbling * 0.3 + pace * 0.1)
    defense_rating = round(defending * 0.8 + physical * 0.2)
    
    return {
        "id": f"fifa:{club_name}:{idx}",
        "name": row.get("NAME", f"Player {idx}").strip(),
        "position": pos,
        "category": cat,
        "club": club_name,
        "overall": rating,
        "attack_rating": attack_rating,
        "defense_rating": defense_rating,
        "att": {
            "pace": pace, "shooting": shooting, "passing": passing,
            "dribbling": dribbling, "defending": defending, "physical": physical,
        },
        "market_value": "N/A",
        "goals_per_90": 0,
        "assists_per_90": 0,
        "appearances": 0,
        "source": "fifa20",
    }


def _pos_to_category(pos):
    pos = pos.upper().strip()
    if pos == "GK":
        return "GK"
    if pos in ("CB", "LB", "RB", "LWB", "RWB"):
        return "DF"
    if pos in ("CM", "CDM", "CAM", "LM", "RM"):
        return "MF"
    if pos in ("ST", "CF", "LW", "RW"):
        return "FW"
    # FIFA uses abbreviations like "LCB", "RCB" etc
    if "B" in pos and pos != "CM":
        return "DF"
    if "M" in pos:
        return "MF"
    if any(p in pos for p in ("ST", "CF", "LW", "RW", "F")):
        return "FW"
    return "MF"


def find_fifa_players(club_name):
    """
    # Find FIFA20 players for a club using fuzzy name matching. Returns list of player dicts, or empty if no match.
    """
    fifa = _load_fifa()
    
    # Try exact match first
    key = club_name.lower().strip()
    if key in fifa:
        return [_fifa_to_player(r, club_name, i) for i, r in enumerate(fifa[key])]
    
    # Try partial match
    for fifa_club, players in fifa.items():
        # Check if club_name is substring of fifa_club or vice versa
        if key in fifa_club or fifa_club in key:
            return [_fifa_to_player(r, club_name, i) for i, r in enumerate(players)]
    
    # Try word-level match
    words = key.split()
    if len(words) >= 2:
        for fifa_club, players in fifa.items():
            matches = sum(1 for w in words if w in fifa_club)
            if matches >= len(words) * 0.5:
                return [_fifa_to_player(r, club_name, i) for i, r in enumerate(players)]
    
    return []


def generate_squad_from_fifa(club_name):
    """Generate squad: FIFA data first, estimator fallback"""
    # 1. Try FIFA20 data
    players = find_fifa_players(club_name)
    if players:
        # Sort by rating, keep top 25
        players.sort(key=lambda x: x["overall"], reverse=True)
        return players[:25]
    
    # 2. Fallback to fixture-based estimator
    from engine.squad_estimator import generate_squad_from_fixtures
    return generate_squad_from_fixtures(club_name)


if __name__ == "__main__":
    for team in ["Stockport", "Barnsley", "AFC Wimbledon", "Bolton", "Man City"]:
        squad = generate_squad_from_fifa(team)
        src = squad[0]["source"] if squad else "none"
        print(f"\n{team}: {len(squad)} players [{src}]")
        for p in squad[:3]:
            att = p.get("att", {})
            att_str = f" PAC:{att.get('pace','?')} SHO:{att.get('shooting','?')} PAS:{att.get('passing','?')}" if att else ""
            print(f"  {p['name']} ({p['position']}) OVR:{p['overall']} ATK:{p['attack_rating']} DEF:{p['defense_rating']}{att_str}")

