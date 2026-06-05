# -*- coding: utf-8 -*-
"""Team name mapping service - unifies team names across sources."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import defaultdict
from data.mysql_client import query

DB_PRED = "football_pred"
DB_ODDS = "football_odds"

# Cache for name mapping (refresh every hour)
_mapping_cache = None
_mapping_time = 0
_MAPPING_TTL = 3600


def build_name_mapping():
    """
    Build unified team name mapping from 3 sources.
    Returns: { normalized_name: { "fixture_name": ..., "tm_name": ..., "tm_id": ... } }
    Cached for 1 hour.
    """
    global _mapping_cache, _mapping_time

    # Return cached if fresh
    if _mapping_cache and (time.time() - _mapping_time < _MAPPING_TTL):
        return _mapping_cache

    mapping = defaultdict(dict)

    # 1. Collect all team names from fixtures
    fixture_rows = query(
        "SELECT DISTINCT league_code, home_team FROM fixtures "
        "UNION SELECT DISTINCT league_code, away_team FROM fixtures",
        db=DB_PRED
    )
    for r in fixture_rows:
        name = r["home_team"]
        norm = normalize(name)
        mapping[norm]["fixture_name"] = name
        if "leagues" not in mapping[norm]:
            mapping[norm]["leagues"] = set()
        mapping[norm]["leagues"].add(r.get("league_code", "?"))

    # 2. Match with tm_clubs
    tm_clubs = query("SELECT club_id, name, domestic_competition_id FROM tm_clubs", db=DB_PRED)

    for norm_name, entry in mapping.items():
        fixture_name = entry.get("fixture_name", "")
        if not fixture_name:
            continue
        for tm in tm_clubs:
            tm_norm = normalize(tm["name"])
            if fixture_name.lower() in tm["name"].lower() or tm_norm in norm_name or norm_name in tm_norm:
                entry["tm_name"] = tm["name"]
                entry["tm_id"] = tm["club_id"]
                entry["tm_league"] = tm["domestic_competition_id"]
                break

    # 3. Supplement from football_odds
    odds_teams = query("SELECT DISTINCT league_code, home_team FROM matches", db=DB_ODDS)

    for r in odds_teams:
        name = r["home_team"]
        norm = normalize(name)
        if norm not in mapping:
            mapping[norm]["fixture_name"] = name
            mapping[norm]["leagues"] = {r["league_code"]}

    # Convert sets to lists for JSON
    result = {}
    for k, v in mapping.items():
        v["leagues"] = sorted(list(v["leagues"])) if "leagues" in v else []
        result[k] = dict(v)

    # Update cache
    _mapping_cache = result
    _mapping_time = time.time()

    return result


def normalize(name):
    """Normalize team name for matching."""
    if not name:
        return ""
    return name.lower().strip().replace(" ", "").replace(".", "").replace("-", "").replace("'", "")


def search_team(query_str):
    """Search for a team across all sources."""
    mapping = build_name_mapping()
    q = normalize(query_str)
    results = []
    for norm, entry in mapping.items():
        if q in norm or norm in q:
            results.append(entry)
    return results
