"""
Improved generic squad generator — uses real name patterns
and team-level stats from fixtures to calibrate ratings.
"""
import sys, os, random, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query

# Realistic name pools by position (common football names)
GK_NAMES = ["Martinez", "Sanchez", "Costa", "Oliveira", "Ferreira", "Mueller", "Jensen", "Andersen", "Nielsen"]
DF_NAMES = ["Silva", "Santos", "Pereira", "Rodriguez", "Garcia", "Thompson", "Campbell", "Williams", "Davies"]
MF_NAMES = ["Fernandes", "Gonzalez", "Lopez", "Torres", "Moreno", "Henderson", "Mitchell", "Bennett", "Cooper"]
FW_NAMES = ["Souza", "Ribeiro", "Almeida", "Carvalho", "Nunes", "Walker", "Johnson", "Roberts", "Edwards"]

FIRST_NAMES = ["Lucas","Gabriel","Mateo","Diego","Pedro","Carlos","Marco","Rafael","Bruno","Miguel",
               "James","Thomas","Daniel","Harry","Jack","Oliver","Charlie","George","William","Henry"]

def _get_team_strength(team_name):
    """Estimate team strength from fixture results (goals scored/conceded)"""
    rows = query("""
        SELECT 
            AVG(CASE WHEN home_team=%s THEN home_score ELSE away_score END) as avg_scored,
            AVG(CASE WHEN home_team=%s THEN away_score ELSE home_score END) as avg_conceded,
            COUNT(*) as games
        FROM fixtures WHERE (home_team=%s OR away_team=%s) AND status='finished'
    """, [team_name, team_name, team_name, team_name], db="football_pred")
    
    if rows and rows[0]["games"] and rows[0]["games"] > 3:
        r = rows[0]
        avg_for = float(r["avg_scored"] or 1.0)
        avg_against = float(r["avg_conceded"] or 1.0)
        # Scale: ~1.0 gpg = avg team
        attack_strength = min(max(avg_for / 1.4, 0.3), 1.7)
        defense_strength = min(max((2.5 - avg_against) / 1.4, 0.3), 1.7)
        return attack_strength, defense_strength, r["games"]
    return 1.0, 1.0, 0


def generate_squad_from_fixtures(club_name):
    """Generate a realistic squad using team performance data"""
    atk_str, def_str, games = _get_team_strength(club_name)
    random.seed(int(__import__("hashlib").md5(club_name.encode()).hexdigest(), 16) % 10000)  # Deterministic per club
    
    players = []
    name_pools = {"GK": GK_NAMES, "DF": DF_NAMES, "MF": MF_NAMES, "FW": FW_NAMES}
    
    templates = [
        ("GK", 2, 62, 72),   # category, count, base_ovr, base_def
        ("DF", 6, 64, 74),
        ("MF", 5, 65, 55),
        ("FW", 4, 66, 38),
    ]
    
    idx = 0
    for cat, count, base_ovr, base_def in templates:
        for _ in range(count):
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(name_pools[cat])
            name = f"{fname} {lname}"
            
            # Adjust ratings based on team strength
            if cat == "GK":
                adj = def_str
                ovr = int(base_ovr * adj + random.randint(-3, 3))
                atk = int(15 * atk_str + random.randint(-2, 2))
                df = int(base_def * def_str + random.randint(-3, 3))
                pos = "Goalkeeper"
            elif cat == "DF":
                adj = def_str
                ovr = int(base_ovr * adj + random.randint(-5, 5))
                atk = int(30 * atk_str + random.randint(-5, 5))
                df = int(base_def * def_str + random.randint(-5, 5))
                pos = random.choice(["Centre-Back", "Left-Back", "Right-Back"])
            elif cat == "MF":
                adj = (atk_str + def_str) / 2
                ovr = int(base_ovr * adj + random.randint(-5, 5))
                atk = int(55 * atk_str + random.randint(-5, 5))
                df = int(base_def * def_str + random.randint(-5, 5))
                pos = random.choice(["Central Midfield", "Defensive Midfield", "Attacking Midfield"])
            else:  # FW
                adj = atk_str
                ovr = int(base_ovr * adj + random.randint(-5, 5))
                atk = int(78 * atk_str + random.randint(-5, 5))
                df = int(base_def * def_str + random.randint(-5, 5))
                pos = random.choice(["Centre-Forward", "Left Winger", "Right Winger"])
            
            ovr = max(40, min(85, ovr))
            atk = max(10, min(90, atk))
            df = max(10, min(90, df))
            
            players.append({
                "id": f"est:{club_name}:{idx}",
                "name": name,
                "position": pos,
                "category": cat,
                "club": club_name,
                "overall": ovr,
                "attack_rating": atk,
                "defense_rating": df,
                "att": None,
                "market_value": "N/A",
                "goals_per_90": round(atk_str * 0.3 + random.random() * 0.3, 2),
                "assists_per_90": round(atk_str * 0.15 + random.random() * 0.2, 2),
                "appearances": games,
                "source": "estimated",
            })
            idx += 1
    
    players.sort(key=lambda x: x["overall"], reverse=True)
    return players


if __name__ == "__main__":
    for team in ["Stockport", "Man City", "AFC Wimbledon"]:
        squad = generate_squad_from_fixtures(team)
        print(f"\n{team} ({len(squad)} players):")
        atk_str, def_str, games = _get_team_strength(team)
        print(f"  Strength: atk={atk_str:.2f}, def={def_str:.2f}, games={games}")
        for p in squad[:3]:
            print(f"  {p['name']} ({p['position']}) OVR:{p['overall']} ATK:{p['attack_rating']} DEF:{p['defense_rating']}")
