"""
历史盘口匹配引擎
根据当前比赛赔率，搜索历史上相似盘口的比赛及其结果。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import time as _time
from data.mysql_client import query

import threading as _threading
_odds_cache = {}
_odds_cache_lock = _threading.Lock()
_ODDS_TTL = 600  # 10 minutes



def find_similar_odds_matches(home_team, away_team, league, threshold=0.08):
    """
    找到与当前比赛赔率相似的历史比赛
    
    Args:
        threshold: 赔率偏差阈值（如 0.08 = ±8%）
    
    Returns: {
        current_odds: {b365h, b365d, b365a},
        similar_count: N,
        outcomes: {H: N, D: N, A: N},
        avg_goals: {home, away},
        top_scores: [{score, count}],
        matches: [{home, away, score, odds}]
    }
    """
    # Check cache
    cache_key = (home_team, away_team, league)
    if cache_key in _odds_cache:
        ts, data = _odds_cache[cache_key]
        if _time.time() - ts < _ODDS_TTL:
            return data

    # 1. 获取当前比赛的赔率
    current = query("""
        SELECT m.id, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa
        FROM matches m
        JOIN odds o ON m.id = o.match_id
        WHERE m.home_team = %s AND m.away_team = %s
          AND m.league_code = %s AND m.fthg IS NULL
        LIMIT 1
    """, [home_team, away_team, league])

    if not current:
        # 尝试用最近一场有赔率的比赛
        current = query("""
            SELECT m.id, o.b365h, o.b365d, o.b365a, o.psh, o.psd, o.psa
            FROM matches m
            JOIN odds o ON m.id = o.match_id
            WHERE m.home_team = %s AND m.away_team = %s
              AND m.league_code = %s AND m.fthg IS NOT NULL
            ORDER BY m.match_date DESC LIMIT 1
        """, [home_team, away_team, league])

    if not current:
        return None

    c = current[0]
    b365h = float(c["b365h"] or 0)
    b365d = float(c["b365d"] or 0)
    b365a = float(c["b365a"] or 0)

    if not (b365h and b365d and b365a):
        return None

    # 2. 搜索赔率相似的历史比赛（同联赛，已完赛）
    h_lo = b365h * (1 - threshold)
    h_hi = b365h * (1 + threshold)
    d_lo = b365d * (1 - threshold)
    d_hi = b365d * (1 + threshold)
    a_lo = b365a * (1 - threshold)
    a_hi = b365a * (1 + threshold)

    similar = query("""
        SELECT m.home_team, m.away_team, m.fthg, m.ftag, m.ftr, m.match_date,
               o.b365h, o.b365d, o.b365a,
               ABS(o.b365h - %s) + ABS(o.b365d - %s) + ABS(o.b365a - %s) AS dist
        FROM matches m
        JOIN odds o ON m.id = o.match_id
        WHERE m.league_code = %s
          AND m.fthg IS NOT NULL
          AND o.b365h BETWEEN %s AND %s
          AND o.b365d BETWEEN %s AND %s
          AND o.b365a BETWEEN %s AND %s
        ORDER BY dist
        LIMIT 30
    """, [b365h, b365d, b365a, league, h_lo, h_hi, d_lo, d_hi, a_lo, a_hi])

    if not similar:
        return None

    # 3. 统计结果
    outcomes = {"H": 0, "D": 0, "A": 0}
    total_hg = 0
    total_ag = 0
    scores = {}

    for m in similar:
        ftr = m["ftr"]
        if ftr in outcomes:
            outcomes[ftr] += 1
        total_hg += (m["fthg"] or 0)
        total_ag += (m["ftag"] or 0)
        score = f"{m['fthg']}-{m['ftag']}"
        scores[score] = scores.get(score, 0) + 1

    n = len(similar)
    top_scores = sorted(scores.items(), key=lambda x: -x[1])[:5]

    # 4. 相似度评分
    similarity = round(1 - (sum(
        abs(float(m["b365h"]) - b365h) / b365h +
        abs(float(m["b365d"]) - b365d) / b365d +
        abs(float(m["b365a"]) - b365a) / b365a
        for m in similar
    ) / (n * 3)), 3)

    result = {
        "current_odds": {
            "home": round(b365h, 2),
            "draw": round(b365d, 2),
            "away": round(b365a, 2),
        },
        "threshold": f"±{int(threshold * 100)}%",
        "similar_count": n,
        "similarity": similarity,
        "outcomes": {
            "home_win": round(outcomes["H"] / n, 3),
            "draw": round(outcomes["D"] / n, 3),
            "away_win": round(outcomes["A"] / n, 3),
            "home_count": outcomes["H"],
            "draw_count": outcomes["D"],
            "away_count": outcomes["A"],
        },
        "avg_goals": {
            "home": round(total_hg / n, 2),
            "away": round(total_ag / n, 2),
        },
        "top_scores": [{"score": s, "count": c, "pct": round(c / n, 3)} for s, c in top_scores],
        "sample_matches": [
            {
                "home": m["home_team"],
                "away": m["away_team"],
                "score": f"{m['fthg']}-{m['ftag']}",
                "result": m["ftr"],
                "odds": f"{float(m['b365h']):.2f}/{float(m['b365d']):.2f}/{float(m['b365a']):.2f}",
                "date": str(m["match_date"]) if m.get("match_date") else "",
            }
            for m in similar[:8]
        ],
    }
    _odds_cache[cache_key] = (_time.time(), result)
    return result
