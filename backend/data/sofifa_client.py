"""SoFIFA 球员数据客户端 — 封装 soccerdata，提供球员搜索和属性查询"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SOFIFA_CACHE
import pandas as pd
import json
import glob

def _row_to_playercard(row, source):
    """将 DataFrame 行转为 PlayerCard dict"""
    att = {
        "pace": int(row.get("pace", 50) or 50),
        "shooting": int(row.get("shooting", 50) or 50),
        "passing": int(row.get("passing", 50) or 50),
        "dribbling": int(row.get("dribbling", 50) or 50),
        "defending": int(row.get("defending", 50) or 50),
        "physical": int(row.get("physical", 50) or 50),
    }
    overall = int(row.get("overall", 50) or 50)
    return {
        "name": str(row.get("name", "")),
        "source": source,
        "position": str(row.get("position", "CM")),
        "att": att,
        "attack_rating": round(att["shooting"] * 0.6 + att["dribbling"] * 0.3 + att["pace"] * 0.1),
        "defense_rating": round(att["defending"] * 0.8 + att["physical"] * 0.2),
        "overall": overall,
        "club": str(row.get("club", "")),
        "market_value": str(row.get("value", "")),
    }

def fetch_league_players(league="Premier League", version="latest"):
    """
    用 soccerdata 抓取某联赛所有球员的 FIFA 评分
    返回 list[PlayerCard]
    """
    try:
        from soccerdata import SoFIFA
        sofifa = SoFIFA(
            leagues=league,
            versions=version,
            data_dir=SOFIFA_CACHE,
            no_store=False,
        )
        df = sofifa.read_players()
        return [_row_to_playercard(row, "sofifa") for _, row in df.iterrows()]
    except Exception as e:
        print(f"SoFIFA fetch failed: {e}")
        return []

def search_player(name, league=None):
    """
    搜索球员，先在缓存找，找不到抓取。
    如果 SoFIFA 不可用（无 Chrome），返回 None。
    """
    # 先查缓存
    cache_files = glob.glob(os.path.join(SOFIFA_CACHE, "**", "players*.csv"), recursive=True)
    if cache_files:
        df = pd.concat([pd.read_csv(f) for f in cache_files])
        matches = df[df["name"].str.contains(name, case=False, na=False)]
        if not matches.empty:
            return _row_to_playercard(matches.iloc[0], "sofifa")

    # 缓存未命中，尝试在线抓取
    if league:
        return search_player_online(name, league)

    return None

def search_player_online(name, league="Premier League"):
    """在线抓取并搜索球员"""
    players = fetch_league_players(league)
    for p in players:
        if name.lower() in p["name"].lower():
            return p
    return None

def get_cached_players():
    """读取所有已缓存的球员"""
    cache_files = glob.glob(os.path.join(SOFIFA_CACHE, "**", "players*.csv"), recursive=True)
    if not cache_files:
        return []
    df = pd.concat([pd.read_csv(f) for f in cache_files])
    return [_row_to_playercard(row, "sofifa") for _, row in df.iterrows()]
