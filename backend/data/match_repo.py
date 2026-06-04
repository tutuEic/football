"""比赛数据仓库 — 从 football_odds 读取历史数据"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.mysql_client import query

def get_matches_for_training(league_code, seasons):
    """获取指定联赛和赛季的比赛用于训练 DC 模型"""
    if isinstance(seasons, str):
        seasons = [seasons]
    placeholders = ','.join(['%s'] * len(seasons))
    sql = f"""
        SELECT home_team AS home, away_team AS away,
               fthg AS home_goals, ftag AS away_goals
        FROM matches
        WHERE league_code=%s AND season IN ({placeholders})
          AND fthg IS NOT NULL AND ftag IS NOT NULL
    """
    return query(sql, [league_code] + list(seasons))

def get_all_leagues():
    rows = query("SELECT DISTINCT league_code FROM matches ORDER BY league_code")
    return [r["league_code"] for r in rows]

def get_seasons(league_code):
    """获取某联赛的所有赛季，返回 list[str]"""
    rows = query(
        "SELECT DISTINCT season FROM matches WHERE league_code=%s ORDER BY season",
        [league_code]
    )
    return [r["season"] for r in rows]

def get_upcoming_matches(league_code=None, limit=50):
    """获取未来赛程（match_date IS NULL 即尚未比赛）"""
    if league_code:
        sql = """
            SELECT m.*, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa,
                   o.avgh, o.avgd, o.avga
            FROM matches m
            LEFT JOIN odds o ON m.id = o.match_id
            WHERE m.league_code=%s AND m.match_date IS NULL
            LIMIT %s
        """
        return query(sql, [league_code, limit])
    else:
        sql = """
            SELECT m.*, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa,
                   o.avgh, o.avgd, o.avga
            FROM matches m
            LEFT JOIN odds o ON m.id = o.match_id
            WHERE m.match_date IS NULL
            LIMIT %s
        """
        return query(sql, [limit])

def get_match_by_id(match_id):
    """获取单场比赛详情（含赔率）"""
    sql = """
        SELECT m.*, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa,
               o.avgh, o.avgd, o.avga
        FROM matches m
        LEFT JOIN odds o ON m.id = o.match_id
        WHERE m.id = %s
    """
    rows = query(sql, [match_id])
    return rows[0] if rows else None

def get_team_names(league_code=None):
    """获取球队名列表"""
    if league_code:
        return query(
            "SELECT DISTINCT home_team AS name FROM matches WHERE league_code=%s ORDER BY home_team",
            [league_code]
        )
    return query("SELECT DISTINCT home_team AS name FROM matches ORDER BY home_team")
