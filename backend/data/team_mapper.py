"""
球队名映射服务 — 统一 football-data.co.uk / Transfermarkt / football_odds 三种球队名
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from collections import defaultdict

DB_PRED = "football_pred"
DB_ODDS = "football_odds"

def get_conn(db=DB_PRED):
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASS", ""),
        database=db,
        charset="utf8mb4",
    )

def build_name_mapping():
    """
    构建三源球队名统一映射:
    - fixtures 表 (football-data.co.uk 简名, 如 "Stockport")
    - tm_clubs 表 (Transfermarkt 全名, 如 "Stockport County Football Club")  
    - football_odds.matches (历史数据名)
    
    返回: { normalized_name: { "fixture_name": ..., "tm_name": ..., "tm_id": ... } }
    """
    conn_pred = get_conn(DB_PRED)
    conn_odds = get_conn(DB_ODDS)
    cur_p = conn_pred.cursor(dictionary=True)
    cur_o = conn_odds.cursor(dictionary=True)

    mapping = defaultdict(dict)

    # 1. 从 fixtures 收集所有球队名（按联赛分组）
    cur_p.execute("SELECT DISTINCT league_code, home_team FROM fixtures UNION SELECT DISTINCT league_code, away_team FROM fixtures")
    for r in cur_p.fetchall():
        name = r["home_team"]  # or away_team
        norm = normalize(name)
        mapping[norm]["fixture_name"] = name
        if "leagues" not in mapping[norm]:
            mapping[norm]["leagues"] = set()
        mapping[norm]["leagues"].add(r.get("league_code", "?"))

    # 2. 从 tm_clubs 匹配（用名称包含关系）
    cur_p.execute("SELECT club_id, name, domestic_competition_id FROM tm_clubs")
    tm_clubs = cur_p.fetchall()

    for norm_name, entry in mapping.items():
        fixture_name = entry.get("fixture_name", "")
        if not fixture_name:
            continue
        for tm in tm_clubs:
            tm_norm = normalize(tm["name"])
            # 匹配逻辑: fixture名包含在TM名中，或TM名包含fixture名
            if fixture_name.lower() in tm["name"].lower() or tm_norm in norm_name or norm_name in tm_norm:
                entry["tm_name"] = tm["name"]
                entry["tm_id"] = tm["club_id"]
                entry["tm_league"] = tm["domestic_competition_id"]
                break

    # 3. 从 football_odds 补充
    cur_o.execute("SELECT DISTINCT league_code, home_team FROM matches")
    odds_teams = cur_o.fetchall()

    # 添加 football_odds 独有的球队
    for r in odds_teams:
        name = r["home_team"]
        norm = normalize(name)
        if norm not in mapping:
            mapping[norm]["fixture_name"] = name
            mapping[norm]["leagues"] = {r["league_code"]}

    cur_p.close(); cur_o.close()
    conn_pred.close(); conn_odds.close()

    #  Convert sets to lists for JSON
    result = {}
    for k, v in mapping.items():
        v["leagues"] = sorted(list(v["leagues"])) if "leagues" in v else []
        result[k] = dict(v)

    return result


def normalize(name):
    """标准化球队名用于匹配"""
    if not name:
        return ""
    return name.lower().strip().replace(" ", "").replace(".", "").replace("-", "").replace("'", "")


def search_team(name, mapping=None):
    """搜索球队，返回统一信息"""
    if mapping is None:
        mapping = build_name_mapping()

    norm = normalize(name)
    results = []

    # 精确匹配
    if norm in mapping:
        results.append(mapping[norm])

    # 模糊匹配
    for key, entry in mapping.items():
        if norm in key or key in norm:
            if entry not in results:
                results.append(entry)

    return results[:20]


# ===== 联赛编码映射 =====
FBD_TO_TM = {
    # football-data.co.uk → Transfermarkt
    "E0": "GB1",   # 英超 → Premier League
    "E1": "GB2",   # 英冠 → Championship
    "E2": "GB3",   # 英甲 → League One
    "E3": "GB4",   # 英乙 → League Two
    "SP1": "ES1",  # 西甲 → La Liga
    "SP2": "ES2",  # 西乙 → La Liga 2
    "D1": "L1",    # 德甲 → Bundesliga
    "D2": "L2",    # 德乙 → 2.Bundesliga
    "I1": "IT1",   # 意甲 → Serie A
    "I2": "IT2",   # 意乙 → Serie B
    "F1": "FR1",   # 法甲 → Ligue 1
    "F2": "FR2",   # 法乙 → Ligue 2
    "N1": "NL1",   # 荷甲 → Eredivisie
    "P1": "PO1",   # 葡超 → Liga Portugal
    "B1": "BE1",   # 比甲 → Pro League
    "T1": "TR1",   # 土超 → Super Lig
    "SC0": "SC1",  # 苏超 → Premiership
    "G1": "GR1",   # 希超 → Super League
    "USA": "MLS1", # MLS
    "JPN": "JAP1", # J联赛
}

TM_TO_FBD = {v: k for k, v in FBD_TO_TM.items()}


if __name__ == "__main__":
    mapping = build_name_mapping()
    print(f"Total teams mapped: {len(mapping)}")

    # 测试
    for name in ["Stockport", "Stockport County", "斯托克港", "Man City", "Manchester City"]:
        results = search_team(name, mapping)
        print(f"\n'{name}':")
        for r in results[:3]:
            print(f"  fixture={r.get('fixture_name')}, tm={r.get('tm_name')}, id={r.get('tm_id')}, leagues={r.get('leagues')}")
