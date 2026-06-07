"""
FlashScore fixture scraper — 抓取缺失的末轮比赛
flashscore.com 通过 XHR API 提供结构化数据
"""
import os, re, json, time
from data.http_utils import safe_get
import mysql.connector
from datetime import datetime

HEADERS = {"X-Requested-With": "XMLHttpRequest"}

# FlashScore league IDs (found in their URL patterns)
# https://www.flashscore.com/football/england/premier-league/
FLASHSCORE_LEAGUES = {
    "E0": {"name": "premier-league", "country": "england", "expected": 380},
    "SP1": {"name": "laliga", "country": "spain", "expected": 380},
    "I1": {"name": "serie-a", "country": "italy", "expected": 380},
    "F1": {"name": "ligue-1", "country": "france", "expected": 306},
    "F2": {"name": "ligue-2", "country": "france", "expected": 306},
    "SP2": {"name": "laliga2", "country": "spain", "expected": 462},
}


def fetch_flashscore_league(league_code, league_info):
    """从 FlashScore 抓取联赛完整赛程"""
    country = league_info["country"]
    name = league_info["name"]
    url = f"https://www.flashscore.com/football/{country}/{name}/results/"

    try:
        r = safe_get(url, headers=HEADERS, label="flashscore-league")
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}")
            return []

        #  Extract match data from the page
        # FlashScore stores data in: cjs.initialFeeds["summary-results"] = { data: `...` }
        #  Also try the summary-results feed
        match = re.search(r'initialFeeds\[\"summary-results\"\]\s*=\s*\{[^}]*data:\s*`([^`]+)`', r.text)
        if not match:
            match = re.search(r"initialFeeds\['summary-results'\]\s*=\s*\{[^}]*data:\s*`([^`]+)`", r.text)
        if not match:
            print(f"  No results feed found")
            return []

        raw = match.group(1)
        matches = parse_flashscore_data(raw, league_code)
        print(f"  Parsed {len(matches)} matches from FlashScore")
        return matches

    except Exception as e:
        print(f"  Error: {e}")
        return []


def parse_flashscore_data(raw, league_code):
    """解析 FlashScore 的编码数据格式（修复版）"""
    parts = raw.split("¬")
    matches = []
    current = None

    for part in parts:
        if "÷" not in part:
            continue
        key, _, val = part.partition("÷")

        if key == "~AA" or key == "AA":
            if current and current.get("home_team"):
                current["league_code"] = league_code
                matches.append(current)
            current = {}
            continue

        if current is None:
            continue

        if key == "AE":
            current["home_team"] = val
        elif key == "AF":
            current["away_team"] = val
        elif key == "AD":
            try:
                ts = int(val)
                current["match_date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except Exception:
                pass
        elif key == "AG":
            try:
                current["home_score"] = int(val)
            except Exception:
                current["home_score"] = None
        elif key == "AH":
            try:
                current["away_score"] = int(val)
            except Exception:
                current["away_score"] = None
        elif key == "BC":
            current["match_time"] = val
        elif key == "ER":
            current["round"] = val

    if current and current.get("home_team"):
        current["league_code"] = league_code
        matches.append(current)

    return matches


def fill_missing_fixtures():
    """主函数：抓取缺失比赛并入库"""
    from data.mysql_client import get_connection
    conn = get_connection(db="football_pred")
    cur = conn.cursor()

    for lc, info in FLASHSCORE_LEAGUES.items():
        # Check current count
        cur.execute("SELECT COUNT(*) FROM fixtures WHERE league_code=%s", [lc])
        current_count = cur.fetchone()[0]
        expected = info["expected"]
        missing = expected - current_count

        if missing <= 0:
            print(f"{lc}: complete ({current_count}/{expected})")
            continue

        print(f"\n{lc} ({info['name']}): {current_count}/{expected}, missing {missing}")
        print(f"  Fetching from FlashScore...")

        matches = fetch_flashscore_league(lc, info)
        time.sleep(1)  # Polite delay between pages  # Polite delay between pages

        # Find matches we don't already have
        new_count = 0
        for m in matches:
            # Check if exists
            cur.execute("""
                SELECT id FROM fixtures
                WHERE league_code=%s AND home_team=%s AND away_team=%s AND match_date=%s
            """, [lc, m.get("home_team"), m.get("away_team"), m.get("match_date")])

            if cur.fetchone():
                continue  # Already exists

            # Insert new fixture
            home_score = m.get("home_score")
            away_score = m.get("away_score")
            status = "finished" if home_score is not None else "scheduled"

            try:
                cur.execute("""
                    INSERT INTO fixtures (league_code, season, match_date, match_time,
                        home_team, away_team, status, home_score, away_score, minute,
                        source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    lc, "2526", m.get("match_date"), m.get("match_time", ""),
                    m.get("home_team"), m.get("away_team"),
                    status, home_score, away_score,
                    90 if status == "finished" else 0,
                    "flashscore"
                ])
                new_count += 1
            except Exception as e:
                print(f"    Insert error: {e} | {m.get('home_team','?')} vs {m.get('away_team','?')}")

        conn.commit()
        print(f"  Added {new_count} new fixtures")

        time.sleep(3)  # Rate limit between leagues

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    fill_missing_fixtures()
