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
import logging
import re
import time
import threading
from datetime import datetime, date
from data.mysql_client import query, execute
from data.http_utils import safe_get
import mysql.connector

DB = "football_pred"
HEADERS = {}  # Deprecated: use http_utils.get_session()
logger = logging.getLogger(__name__)

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
        if r is None:
            return []
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
        if r is not None and r.status_code == 200:
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


def _safe_int(value, default=None):
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).strip().replace("'", "")))
    except (TypeError, ValueError):
        return default


def _normalize_team_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _parse_minute(value):
    if value is None:
        return 0
    text = str(value)
    if text.lower() in {"ht", "half time"}:
        return 45
    if text.lower() in {"ft", "full time", "match finished"}:
        return 90
    match = re.search(r"\d+", text)
    return _safe_int(match.group(0), 0) if match else 0


def _status_from_source(raw_status, minute, home_score, away_score):
    status = (raw_status or "").strip().lower()
    if status in {"match finished", "finished", "ft", "full time", "after extra time"}:
        return "finished"
    if status in {"not started", "scheduled", "ns"}:
        return "scheduled"
    if status in {"postponed", "cancelled", "canceled", "abandoned"}:
        return "postponed"
    if minute > 0 or home_score is not None or away_score is not None:
        return "live"
    return "today"


def _extract_live_match(raw: dict) -> dict | None:
    """Normalize a live-score provider row into the local shape."""
    home = raw.get("home_team") or raw.get("strHomeTeam") or raw.get("AE")
    away = raw.get("away_team") or raw.get("strAwayTeam") or raw.get("AF")
    if not home or not away:
        return None

    home_score = _safe_int(
        raw.get("home_score", raw.get("intHomeScore", raw.get("AG")))
    )
    away_score = _safe_int(
        raw.get("away_score", raw.get("intAwayScore", raw.get("AH")))
    )
    raw_status = (
        raw.get("status")
        or raw.get("strStatus")
        or raw.get("strProgress")
        or raw.get("AX")
        or ""
    )
    minute = _parse_minute(raw.get("minute") or raw.get("intMinute") or raw.get("strProgress") or raw.get("AX"))
    status = _status_from_source(raw_status, minute, home_score, away_score)

    return {
        "home_team": home,
        "away_team": away,
        "home_key": _normalize_team_name(home),
        "away_key": _normalize_team_name(away),
        "home_score": home_score,
        "away_score": away_score,
        "minute": minute,
        "status": status,
        "raw_status": raw_status,
    }


def _best_live_match(fixture: dict, live_matches: list[dict]) -> dict | None:
    home_key = _normalize_team_name(fixture.get("home_team"))
    away_key = _normalize_team_name(fixture.get("away_team"))
    for match in live_matches:
        if match["home_key"] == home_key and match["away_key"] == away_key:
            return match
        # Provider naming often includes suffixes; allow contained-name matching.
        if (
            home_key and away_key
            and (home_key in match["home_key"] or match["home_key"] in home_key)
            and (away_key in match["away_key"] or match["away_key"] in away_key)
        ):
            return match
    return None


def _has_fixture_changed(fixture: dict, live_match: dict) -> bool:
    return (
        fixture.get("home_score") != live_match["home_score"]
        or fixture.get("away_score") != live_match["away_score"]
        or fixture.get("minute") != live_match["minute"]
        or fixture.get("status") != live_match["status"]
    )


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

    normalized_live = []
    for row in live_data:
        match = _extract_live_match(row)
        if match:
            normalized_live.append(match)

    updated = []

    for fix in fixtures:
        live_match = _best_live_match(fix, normalized_live)
        if not live_match:
            continue
        if live_match["home_score"] is None or live_match["away_score"] is None:
            continue
        if _has_fixture_changed(fix, live_match):
            check_and_update_status(
                fix["id"],
                live_match["home_score"],
                live_match["away_score"],
                live_match["minute"],
                live_match["status"],
            )
            updated.append({
                **fix,
                "home_score": live_match["home_score"],
                "away_score": live_match["away_score"],
                "minute": live_match["minute"],
                "status": live_match["status"],
            })

    if updated:
        logger.info("[live] Updated %d live fixtures", len(updated))

    # Always return the latest local state so WebSocket clients stay in sync.
    return get_today_status()


def check_and_update_status(fixture_id, home_score, away_score, minute, status):
    """Update a single fixture's live status using connection pool."""
    execute("""
        UPDATE fixtures SET
            home_score = %s, away_score = %s, minute = %s, status = %s,
            updated_at = NOW()
        WHERE id = %s
    """, [home_score, away_score, minute, status, fixture_id])

    # Also insert/update live_matches for detailed stats
    execute("""
        INSERT INTO live_matches (fixture_id, home_score, away_score, minute, status, last_updated)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            home_score = VALUES(home_score),
            away_score = VALUES(away_score),
            minute = VALUES(minute),
            status = VALUES(status),
            last_updated = NOW()
    """, [fixture_id, home_score, away_score, minute, status])


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
            start_time = time.time()
            try:
                # Run poll with timeout (use threading to enforce)
                fixtures = None
                def _do_poll():
                    nonlocal fixtures
                    fixtures = poll_live_scores()

                poll_thread = threading.Thread(target=_do_poll, daemon=True)
                poll_thread.start()
                poll_thread.join(timeout=self.interval * 0.8)  # 80% of interval as timeout

                if poll_thread.is_alive():
                    logger.warning("[live] Poll timed out after %ds, skipping", int(self.interval * 0.8))
                elif fixtures:
                    # Notify WebSocket clients with current state
                    for cb in self.callbacks:
                        try:
                            cb(fixtures)
                        except Exception:
                            pass

            except Exception as e:
                logger.error("[live] Poll error: %s", e)

            # Sleep for remaining interval time
            elapsed = time.time() - start_time
            sleep_time = max(1, self.interval - elapsed)
            time.sleep(sleep_time)

    def register_callback(self, callback):
        self.callbacks.append(callback)


# Singleton
poller = LiveScorePoller(interval=int(os.getenv("LIVE_POLL_INTERVAL", "300")))


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
