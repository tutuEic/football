"""
Fixtures & Results Pipeline 鈥?football-data.co.uk 鏁版嵁閲囬泦
==========================================================
鏁版嵁婧? https://www.football-data.co.uk/ (鍏嶈垂, 32瀹跺崥褰╁叕鍙歌禂鐜? 30+鑱旇禌)
鏇存柊棰戠巼: 姣忓懆2娆★紙鍛ㄤ腑+鍛ㄦ湯璧涘悗锛?
"""
import requests
from data.http_utils import safe_get
import csv
import sys, os
from io import StringIO
from datetime import datetime, date, timedelta
import time

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from data.mysql_client import query, execute
import mysql.connector

DB = "football_pred"

#  All available leagues from football-data.co.uk
LEAGUE_CODES = {
    # England
    "E0": "EPL", "E1": "Championship", "E2": "League One", "E3": "League Two", "EC": "Conference",
    # Scotland
    "SC0": "SPL", "SC1": "Championship", "SC2": "League One", "SC3": "League Two",
    # Germany
    "D1": "Bundesliga", "D2": "2.Bundesliga",
    # Italy
    "I1": "Serie A", "I2": "Serie B",
    # Spain
    "SP1": "La Liga", "SP2": "La Liga 2",
    # France
    "F1": "Ligue 1", "F2": "Ligue 2",
    # Netherlands
    "N1": "Eredivisie",
    # Belgium
    "B1": "Pro League",
    # Portugal
    "P1": "Primeira Liga",
    # Turkey
    "T1": "Super Lig",
    # Greece
    "G1": "Super League",
    # Other
    "USA": "MLS",
    "JPN": "J1 League",
}

SEASONS = ["2526", "2425"]  # Current + last season
BASE_URL = "https://www.football-data.co.uk/mmz4281"

# User-Agent is set globally by http_utils.get_session()
HEADERS = None


def get_conn():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASS", ""),
        database=DB,
        charset="utf8mb4",
    )


def safe_float(val, default=None):
    if val is None or val == "" or val == "None":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    if val is None or val == "" or val == "None":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def fetch_csv(league_code, season):
    """涓嬭浇鍗曚釜鑱旇禌CSV"""
    url = f"{BASE_URL}/{season}/{league_code}.csv"
    try:
        r = safe_get(url, headers=HEADERS, label="football-data")
        if r.status_code == 200 and len(r.text) > 100:
            reader = csv.DictReader(StringIO(r.text))
            return list(reader), reader.fieldnames
        return None, None
    except Exception as e:
        print(f"  Failed: {e}")
        return None, None


def upsert_fixtures(league_code, season, rows):
    """Upsert CSV data into fixtures table."""
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    updated = 0

    for row in rows:
        try:
            home = row.get("HomeTeam", "").strip()
            away = row.get("AwayTeam", "").strip()
            date_str = row.get("Date", "").strip()
            time_str = row.get("Time", "").strip()

            if not home or not away or not date_str:
                continue

            # Parse date (formats: dd/mm/yyyy or dd/mm/yy)
            try:
                parts = date_str.split("/")
                if len(parts) == 3:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    if year < 100:
                        year += 2000
                    match_date = date(year, month, day)
                else:
                    match_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, IndexError):
                continue

            home_goals = safe_int(row.get("FTHG"))
            away_goals = safe_int(row.get("FTAG"))
            result = row.get("FTR", "").strip()

            # Determine status
            if result:
                status = "finished"
            elif match_date > date.today():
                status = "scheduled"
            elif match_date == date.today():
                status = "today"
            else:
                status = "postponed"  # should have result but doesn't

            # Sanity: truncate status to 30 chars
            status = status[:30]

            if status == "finished" or status == "postponed":
                minute = 90
                home_score = home_goals
                away_score = away_goals
                winner = result
            else:
                minute = 0
                home_score = None
                away_score = None
                winner = None

            # Odds
            b365h = safe_float(row.get("B365H"))
            b365d = safe_float(row.get("B365D"))
            b365a = safe_float(row.get("B365A"))

            # Average odds (safer than single bookmaker)
            avgh = safe_float(row.get("AvgH")) or safe_float(row.get("BbAvH")) or b365h
            avgd = safe_float(row.get("AvgD")) or safe_float(row.get("BbAvD")) or b365d
            avga = safe_float(row.get("AvgA")) or safe_float(row.get("BbAvA")) or b365a

            # Over/Under 2.5
            over25 = safe_float(row.get("BbAv>2.5")) or safe_float(row.get("Avg>2.5"))
            under25 = safe_float(row.get("BbAv<2.5")) or safe_float(row.get("Avg<2.5"))

            cur.execute("""
                INSERT INTO fixtures (league_code, season, match_date, match_time,
                    home_team, away_team, status, home_score, away_score, minute, winner,
                    odds_home, odds_draw, odds_away, odds_over25, odds_under25, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    match_time = VALUES(match_time),
                    status = VALUES(status),
                    home_score = COALESCE(VALUES(home_score), home_score),
                    away_score = COALESCE(VALUES(away_score), away_score),
                    minute = VALUES(minute),
                    winner = COALESCE(VALUES(winner), winner),
                    odds_home = COALESCE(VALUES(odds_home), odds_home),
                    odds_draw = COALESCE(VALUES(odds_draw), odds_draw),
                    odds_away = COALESCE(VALUES(odds_away), odds_away),
                    odds_over25 = COALESCE(VALUES(odds_over25), odds_over25),
                    odds_under25 = COALESCE(VALUES(odds_under25), odds_under25),
                    source = 'football-data.co.uk',
                    updated_at = CURRENT_TIMESTAMP
            """, (
                league_code, season, match_date, time_str or None,
                home, away, status, home_score, away_score, minute, winner,
                avgh, avgd, avga, over25, under25,
                "football-data.co.uk"
            ))

            if cur.rowcount == 1:
                inserted += 1
            elif cur.rowcount == 2:
                updated += 1

        except Exception as e:
            print(f"  Row error: {e} | {row.get('HomeTeam','?')} vs {row.get('AwayTeam','?')}")
            continue

    conn.commit()
    cur.close()
    conn.close()
    return inserted, updated


def sync_odds_to_football_odds(league_code, season, rows):
    """涔熸妸鏈€鏂拌禂鐜囧悓姝ュ洖 football_odds.matches 琛紙淇濇寔鍏煎锛"""
    # This is optional 鈥?football_odds already has historical data
    # Only sync if there are matches not yet in that DB
    pass


def refresh_all(leagues=None):
    """瀹屾暣鍒锋柊锛氭媺鍙栨墍鏈夎仈璧涙渶鏂版暟鎹"""
    t0 = time.time()
    total_inserted = 0
    total_updated = 0
    errors = []

    codes = leagues if leagues else list(LEAGUE_CODES.keys())
    season = SEASONS[0]  # Current season

    print(f"Pipeline: refreshing {len(codes)} leagues from football-data.co.uk ({season})...")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for i, code in enumerate(codes):
        name = LEAGUE_CODES.get(code, code)
        print(f"\n[{i+1}/{len(codes)}] {code} ({name})")

        rows, fields = fetch_csv(code, season)
        if not rows:
            # Try previous season
            rows, fields = fetch_csv(code, SEASONS[1])
            if not rows:
                print(f"  No data for {code}")
                errors.append(code)
                continue

        print(f"  Downloaded: {len(rows)} rows, {len(fields) or 0} columns")

        ins, upd = upsert_fixtures(code, season, rows)
        print(f"  DB: {ins} new, {upd} updated")
        total_inserted += ins
        total_updated += upd

        time.sleep(0.5)  # Rate limit

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s. {total_inserted} inserted, {total_updated} updated, {len(errors)} errors")

    # Log to data_refresh_log
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASS", ""),
        database=DB,
        charset="utf8mb4",
    )
    cur = conn.cursor()
    log_status = "ok" if not errors else f"partial-{len(errors)}-errors"
    cur.execute("""
        INSERT INTO data_refresh_log (source, action, records_affected, status, finished_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (
        "football-data.co.uk",
        "refresh_all",
        total_inserted + total_updated,
        log_status[:200]
    ))
    conn.commit()
    cur.close()
    conn.close()

    return total_inserted, total_updated


def get_today_matches():
    """鑾峰彇浠婂ぉ鎵€鏈夋瘮璧涳紙渚涘疄鏃舵湇鍔′娇鐢級"""
    today = date.today().isoformat()
    return query(
        """SELECT * FROM fixtures
           WHERE match_date = %s AND status IN ('scheduled', 'today', 'live')
           ORDER BY league_code, match_time""",
        [today], db=DB
    )


def get_upcoming_matches(league_code=None, days=7, limit=100):
    """鑾峰彇鏈潵N澶╄禌绋"""
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=days)).isoformat()

    if league_code:
        return query("""
            SELECT * FROM fixtures
            WHERE league_code = %s AND match_date BETWEEN %s AND %s
            ORDER BY match_date, match_time
            LIMIT %s
        """, [league_code, start, end, limit], db=DB)
    else:
        return query("""
            SELECT * FROM fixtures
            WHERE match_date BETWEEN %s AND %s
            ORDER BY match_date, league_code, match_time
            LIMIT %s
        """, [start, end, limit], db=DB)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--leagues", nargs="*", help="Specific leagues to refresh")
    p.add_argument("--today", action="store_true", help="Show today's matches")
    p.add_argument("--upcoming", type=int, default=0, help="Show upcoming N days")
    args = p.parse_args()

    if args.today:
        matches = get_today_matches()
        print(f"\nToday's matches ({len(matches)}):")
        for m in matches:
            print(f"  {m['league_code']} {m['home_team']} vs {m['away_team']} {m.get('match_time','')}")
    elif args.upcoming:
        matches = get_upcoming_matches(days=args.upcoming)
        print(f"\nUpcoming {args.upcoming} days ({len(matches)} matches):")
        for m in matches:
            print(f"  {m['match_date']} {m['league_code']} {m['home_team']} vs {m['away_team']}")
    else:
        refresh_all(args.leagues)
