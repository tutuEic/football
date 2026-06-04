"""
Live Match Service — 实时比分采集 + 推送
=========================================
Phase 1: TheSportsDB free API (10 leagues, 100 req/day)
Phase 2: FlashScore scraping (more coverage)

Architecture:
  - Poller: 每60秒抓取今日比赛比分
  - WebSocket: FastAPI 集成，推送比分变化到前端
"""
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import requests
import json
import time
import threading
from datetime import datetime, date
from data.mysql_client import query, execute
import mysql.connector

DB = "football_pred"
HEADERS = {}  # Deprecated: use http_utils.get_session()

# ============================================================
#  Phase 1: TheSportsDB API  (free tier, key required)
#  Sign up: https://www.thesportsdb.com/free_sports_api
# ============================================================
# Leave empty to skip — will automatically fall back to simulated
SPORTSDB_API_KEY = os.getenv("SPORTSDB_API_KEY", "")
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json"


def fetch_livescore_api():
    """Fetch live scores from TheSportsDB (free tier)"""
    if not SPORTSDB_API_KEY or SPORTSDB_API_KEY == "YOUR_KEY":
        print("[live] No TheSportsDB API key — skipping API-based live scores")
        return []

    url = f"{SPORTSDB_BASE}/{SPORTSDB_API_KEY}/latestsoccer.php"
    try:
        r = safe_get(url, label="thesportsdb")
        if r.status_code != 200:
            print(f"[live] API error: {r.status_code}")
            return []
        data = r.json()
        matches = data.get("results", data.get("events", []))
        live = [m for m in matches if m.get("strStatus") not in ("Match Finished", "Not Started", "Postponed")]
        return live
    except Exception as e:
        print(f"[live] API fetch failed: {e}")
        return []


# ============================================================
#  Phase 2: FlashScore scraping
# ============================================================
def fetch_flashscore_live():
    """
    # Scrape live scores from FlashScore. FlashScore exposes a hidden JSON API at /x/feed/. This is lightweight and returns structured JSON.
    """
    try:
        #  FlashScore mobile API endpoint (no auth needed for basic scores)
        url = "https://www.flashscore.com/x/feed/proxy"
        params = {
            "sport": "soccer",
            "ind": "1",  # index page
        }
        r = safe_get(url, headers={
            "X-Requested-With": "XMLHttpRequest",
        }, label="flashscore-live")
        if r.status_code == 200:
            return parse_flashscore_response(r.text)
    except Exception as e:
        print(f"[live] FlashScore fetch failed: {e}")
    return []


def parse_flashscore_response(text):
    """Parse FlashScore's weird protocol response"""
    matches = []
    try:
        # FlashScore returns data in a custom format, split by ¬
        parts = text.split("¬")
        # Extract match data blocks (format: AA÷...¬)
        for part in parts:
            if "AA÷" in part and "AD÷" in part:
                match = {}
                fields = part.split("¬")
                for field in fields:
                    if "÷" in field:
                        key, _, val = field.partition("÷")
                        if key in ("AA", "AC", "AD", "AE", "AG", "AH", "AI", "AJ", "AK", "AX", "BA", "BB"):
                            match[key] = val
                if match:
                    matches.append(match)
    except Exception:
        pass
    return matches


# ============================================================
#  Main polling loop
# ============================================================
def poll_live_scores():
    """
    # Poll live scores and update database. Returns list of changed matches.
    """
    # 1. Get today's scheduled/live matches from DB
    today = date.today().isoformat()
    fixtures = query("""
        SELECT id, league_code, home_team, away_team, match_time,
               home_score, away_score, status, minute
        FROM fixtures
        WHERE match_date = %s
          AND status IN ('scheduled', 'today', 'live')
    """, [today], db=DB)

    if not fixtures:
        return []

    # 2. Try TheSportsDB API first
    live_data = fetch_livescore_api()

    # 3. Fallback to FlashScore
    if not live_data:
        live_data = fetch_flashscore_live()

    #  4. Update DB with scores (some may already be finished)
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"), password=os.getenv("MYSQL_PASS", ""),
        database=DB, charset="utf8mb4"
    )
    cur = conn.cursor()
    updated = []

    for fix in fixtures:
        #  Simulate score progression for now (when no real data available)
        # In production, match fix['home_team'] with live_data
        pass

    conn.commit()
    cur.close()
    conn.close()

    #  If no live data available, at least return today's fixture list return fixtures


def check_and_update_status(fixture_id, home_score, away_score, minute, status):
    """Update a single fixture's live status"""
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"), password=os.getenv("MYSQL_PASS", ""),
        database=DB, charset="utf8mb4"
    )
    cur = conn.cursor()

    cur.execute("""
        UPDATE fixtures SET
            home_score = %s, away_score = %s, minute = %s, status = %s,
            updated_at = NOW()
        WHERE id = %s
    """, [home_score, away_score, minute, status, fixture_id])

    #  Also insert/update live_matches for detailed stats
    cur.execute("""
        INSERT INTO live_matches (fixture_id, home_score, away_score, minute, status, last_updated)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            home_score = VALUES(home_score),
            away_score = VALUES(away_score),
            minute = VALUES(minute),
            status = VALUES(status),
            last_updated = NOW()
    """, [fixture_id, home_score, away_score, minute, status])

    conn.commit()
    cur.close()
    conn.close()


# ============================================================
#  Scheduled polling thread
# ============================================================
class LiveScorePoller:
    """Background thread that polls live scores every 60 seconds"""

    def __init__(self, interval=60):
        self.interval = interval
        self.running = False
        self.thread = None
        self.callbacks = []  # WebSocket clients to notify

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print(f"[live] Poller started (interval={self.interval}s)")

    def stop(self):
        self.running = False

    def _poll_loop(self):
        while self.running:
            try:
                today = date.today().isoformat()
                fixtures = query("""
                    SELECT id, league_code, home_team, away_team, match_time,
                           home_score, away_score, status, minute
                    FROM fixtures
                    WHERE match_date = %s AND status IN ('scheduled', 'today', 'live')
                """, [today], db=DB)

                if fixtures:
                    #  Notify WebSocket clients with current state
                    for cb in self.callbacks:
                        try:
                            cb(fixtures)
                        except Exception:
                            pass

            except Exception as e:
                print(f"[live] Poll error: {e}")

            time.sleep(self.interval)

    def register_callback(self, callback):
        self.callbacks.append(callback)


# Singleton
poller = LiveScorePoller(interval=60)


def get_today_status():
    """Get all today's fixtures with current status"""
    today = date.today().isoformat()
    return query("""
        SELECT f.*, lm.home_shots, lm.away_shots, lm.home_possession, lm.away_possession,
               lm.home_shots_on_target, lm.away_shots_on_target,
               lm.home_corners, lm.away_corners, lm.home_yellow_cards, lm.away_yellow_cards
        FROM fixtures f
        LEFT JOIN live_matches lm ON f.id = lm.fixture_id
        WHERE f.match_date = %s
        ORDER BY f.league_code, f.match_time
    """, [today], db=DB)


if __name__ == "__main__":
    print("Testing live score poller...")
    matches = get_today_status()
    print(f"\nToday's matches ({len(matches)}):")
    for m in matches:
        score = f"{m.get('home_score','-')} - {m.get('away_score','-')}" if m.get('home_score') is not None else "vs"
        print(f"  [{m['status']}] {m['league_code']} {m['home_team']} {score} {m['away_team']} {m.get('match_time','')}")
