"""SoFIFA player data client with caching."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SOFIFA_CACHE
import pandas as pd
import json
import glob
import re
import time

# Cache for player data (refresh every 30 minutes)
_players_cache = None
_players_cache_time = 0
_CACHE_TTL = 1800  # 30 minutes


def _load_players_cached():
    """Load all cached player CSVs with caching."""
    global _players_cache, _players_cache_time
    
    if _players_cache is not None and (time.time() - _players_cache_time < _CACHE_TTL):
        return _players_cache
    
    cache_files = glob.glob(os.path.join(SOFIFA_CACHE, "**", "players*.csv"), recursive=True)
    if not cache_files:
        return pd.DataFrame()
    
    _players_cache = pd.concat([pd.read_csv(f) for f in cache_files])
    _players_cache_time = time.time()
    return _players_cache


def _row_to_playercard(row, source):
    """Convert DataFrame row to PlayerCard dict."""
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
        "overall": overall,
        "attributes": att,
        "source": source,
    }


def search_player(name, league=None):
    """Search for a player in cache, fallback to online fetch."""
    # Use cached data
    df = _load_players_cached()
    if not df.empty:
        escaped = re.escape(name)
        matches = df[df["name"].str.contains(escaped, case=False, na=False)]
        if not matches.empty:
            return _row_to_playercard(matches.iloc[0], "sofifa")

    # Cache miss, try online fetch
    if league:
        return search_player_online(name, league)

    return None


def search_player_online(name, league="Premier League"):
    """Fetch online and search for player."""
    players = fetch_league_players(league)
    for p in players:
        if name.lower() in p["name"].lower():
            return p
    return None


def get_cached_players():
    """Get all cached players."""
    df = _load_players_cached()
    if df.empty:
        return []
    return [_row_to_playercard(row, "sofifa") for _, row in df.iterrows()]


def fetch_league_players(league):
    """Fetch players from a league (placeholder - requires SoFIFA scraping)."""
    # This would need actual SoFIFA scraping implementation
    return []
