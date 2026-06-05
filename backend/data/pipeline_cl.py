# -*- coding: utf-8 -*-
"""
Champions League Data Pipeline - FlashScore

Fetches Champions League fixtures and results from FlashScore.
"""
import sys, os, re, json, time
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from data.http_utils import safe_get
import mysql.connector
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS, CURRENT_SEASON

DB = "football_pred"
LEAGUE_CODE = "CL"

# Derive season string dynamically (e.g. "2526" for the 2025/2026 season).
SEASON_STR = f"{CURRENT_SEASON % 100:02d}{(CURRENT_SEASON + 1) % 100:02d}"

# FlashScore field separators
FIELD_SEP = "\u00AC"  # ?
KV_SEP = "\u00F7"     # ¡Â

FLASHSCORE_URLS = {
    "results": "https://www.flashscore.com/football/europe/champions-league/results/",
    "fixtures": "https://www.flashscore.com/football/europe/champions-league/",
}


def get_conn():
    return mysql.connector.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=DB, charset="utf8mb4",
    )


def _parse_flashscore_data(raw):
    """Parse FlashScore data."""
    records = []
    parts = raw.split("~")
    
    for part in parts:
        fields = {}
        for item in part.split(FIELD_SEP):
            if KV_SEP in item:
                k, _, v = item.partition(KV_SEP)
                fields[k] = v.strip()
        
        if "AA" not in fields or "AD" not in fields:
            continue
        
        ts = fields.get("AD", "")
        if not ts or not ts.isdigit():
            continue
        
        dt = datetime.fromtimestamp(int(ts))
        home = fields.get("AE", fields.get("CX", ""))
        away = fields.get("AF", fields.get("CY", ""))
        
        if not home or not away:
            continue
        
        record = {
            "match_id": fields.get("AA", ""),
            "date": dt.strftime("%Y-%m-%d"),
            "home_team": home,
            "away_team": away,
            "score_h": fields.get("AG", ""),
            "score_a": fields.get("AH", ""),
            "stage": fields.get("ER", ""),
            "note": fields.get("AM", ""),
        }
        records.append(record)
    
    return records


def fetch_cl_results():
    """Fetch completed Champions League matches."""
    url = FLASHSCORE_URLS["results"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = safe_get(url, headers=headers, label="flashscore-cl-results")
        if not r or r.status_code != 200:
            print(f"[CL] Results fetch failed: {r.status_code if r else 'None'}")
            return []
        
        match = re.search(r'initialFeeds\["summary-results"\]\s*=\s*\{[^}]*data:\s*([^]+)', r.text)
        if not match:
            print("[CL] No results data found")
            return []
        
        results = _parse_flashscore_data(match.group(1))
        print(f"[CL] Fetched {len(results)} completed matches")
        return results
    except Exception as e:
        print(f"[CL] Error fetching results: {e}")
        return []


def fetch_cl_fixtures():
    """Fetch upcoming Champions League matches."""
    url = FLASHSCORE_URLS["fixtures"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = safe_get(url, headers=headers, label="flashscore-cl-fixtures")
        if not r or r.status_code != 200:
            print(f"[CL] Fixtures fetch failed: {r.status_code if r else 'None'}")
            return []
        
        # Try summary-fixtures first
        match = re.search(r'initialFeeds\["summary-fixtures"\]\s*=\s*\{[^}]*data:\s*([^]+)', r.text)
        if not match:
            # Fall back to future feed or results feed
            match = re.search(r'initialFeeds\["summary-results"\]\s*=\s*\{[^}]*data:\s*([^]+)', r.text)
        
        if not match:
            print("[CL] No fixtures data found")
            return []
        
        fixtures = _parse_flashscore_data(match.group(1))
        # Filter to future matches only
        today = date.today().strftime("%Y-%m-%d")
        future = [f for f in fixtures if f["date"] >= today]
        print(f"[CL] Fetched {len(future)} upcoming fixtures")
        return future
    except Exception as e:
        print(f"[CL] Error fetching fixtures: {e}")
        return []


def save_to_db(results, fixtures):
    """Save results and fixtures to database using batch operations."""
    conn = get_conn()
    cursor = conn.cursor()
    
    saved_results = 0
    saved_fixtures = 0
    
    try:
        # Batch upsert match results (INSERT ... ON DUPLICATE KEY UPDATE)
        if results:
            values = []
            for m in results:
                values.append((
                    LEAGUE_CODE, SEASON_STR, m["date"], m["home_team"], m["away_team"],
                    m["score_h"], m["score_a"], "finished", "flashscore"
                ))
            
            cursor.executemany(
                """INSERT INTO fixtures (league_code, season, match_date, home_team, away_team, 
                   home_score, away_score, status, source)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                       home_score = VALUES(home_score),
                       away_score = VALUES(away_score),
                       status = VALUES(status),
                       updated_at = NOW()""",
                values
            )
            saved_results = cursor.rowcount
        
        # Batch insert upcoming fixtures (ignore duplicates)
        if fixtures:
            values = []
            for m in fixtures:
                values.append((
                    LEAGUE_CODE, SEASON_STR, m["date"], m["home_team"], m["away_team"], "flashscore"
                ))
            
            cursor.executemany(
                """INSERT IGNORE INTO fixtures (league_code, season, match_date, home_team, away_team, source)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                values
            )
            saved_fixtures = cursor.rowcount
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    
    return saved_results, saved_fixtures



def run_pipeline():
    """Run Champions League pipeline."""
    print("\n" + "=" * 60)
    print("Champions League Data Pipeline")
    print("=" * 60)
    
    results = fetch_cl_results()
    fixtures = fetch_cl_fixtures()
    
    if results or fixtures:
        saved_r, saved_f = save_to_db(results, fixtures)
        print(f"[CL] Saved: {saved_r} results, {saved_f} fixtures")
    else:
        print("[CL] No new data to save")
    
    return results, fixtures


if __name__ == "__main__":
    run_pipeline()
