# -*- coding: utf-8 -*-
"""
Import international match data from public datasets into tm_games.

Data source: martj42/international_results on GitHub
URL: https://raw.githubusercontent.com/martj42/international_results/master/results.csv

This fills the gap for World Cup qualifiers, Euro qualifiers, and other
international tournaments needed by the WC prediction engine.
"""
import csv
import hashlib
import sys
import os
import time
from io import StringIO
from datetime import datetime, date

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query, execute

# Tournament name -> competition_id mapping
TOURNAMENT_MAP = {
    # Major tournaments (already in DB but may have gaps)
    "FIFA World Cup":                "FIWC",
    "UEFA Euro":                     "EURO",
    u"Copa Am\u00e9rica":           "COPA",
    "African Cup of Nations":        "AFAC",
    "AFC Asian Cup":                 "AFCN",

    # Qualifiers (CRITICAL for form calculation)
    "FIFA World Cup qualification":  "WCQL",
    "UEFA Euro qualification":       "EUCON",
    "African Cup of Nations qualification": "AFQL",
    "AFC Asian Cup qualification":   "ACQL",
    "CONCACAF Nations League qualification": "CNLQ",

    # Nations League
    "UEFA Nations League":           "UNL",
    "CONCACAF Nations League":       "CNL",

    # Continental cups
    "Gold Cup":                      "GC",
    "OFC Nations Cup":               "OFC",

    # Friendlies
    "Friendly":                      "FR",
}

DATA_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
START_DATE = "2014-01-01"
END_DATE = "2026-06-01"


def download_data():
    """Download the international results CSV."""
    print(f"Downloading from {DATA_URL}...")
    r = requests.get(DATA_URL, timeout=60)
    r.raise_for_status()
    reader = csv.DictReader(StringIO(r.text))
    rows = list(reader)
    print(f"  Total rows: {len(rows)}")
    return rows


def filter_and_map(rows):
    """Filter by date range and map tournament names to competition_ids."""
    mapped = []
    skipped = set()

    for r in rows:
        d = r.get("date", "")
        if d < START_DATE or d > END_DATE:
            continue

        tournament = r.get("tournament", "")
        comp_id = TOURNAMENT_MAP.get(tournament)

        if not comp_id:
            skipped.add(tournament)
            continue

        home = r.get("home_team", "").strip()
        away = r.get("away_team", "").strip()
        if not home or not away:
            continue

        home_score = r.get("home_score", "")
        away_score = r.get("away_score", "")

        try:
            hg = int(home_score) if home_score else None
            ag = int(away_score) if away_score else None
        except ValueError:
            hg = ag = None

        mapped.append({
            "date": d,
            "competition_id": comp_id,
            "home_team": home,
            "away_team": away,
            "home_goals": hg,
            "away_goals": ag,
            "tournament": tournament,
            "neutral": r.get("neutral", "FALSE") == "TRUE",
        })

    if skipped:
        print(f"  Skipped {len(skipped)} unmapped tournament types:")
        for t in sorted(skipped):
            print(f"    - {t}")

    print(f"  Mapped matches: {len(mapped)}")
    return mapped


def import_to_tm_games(matches):
    """Insert matches into tm_games table."""
    print(f"Importing {len(matches)} matches into tm_games...")

    inserted = 0
    skipped = 0
    errors = 0

    for i, m in enumerate(matches):
        # Generate a unique game_id for international matches
        # Use a large offset to avoid collision with existing TM game_ids
        date_str = m["date"]
        home = m["home_team"]
        away = m["away_team"]

        # Check if match already exists by date + teams (idempotent, avoids hash collision)
        existing = query(
            "SELECT game_id FROM tm_games"
            " WHERE date=%s AND home_club_name=%s AND away_club_name=%s AND competition_id=%s",
            [date_str, home, away, m["competition_id"]], db="football_pred"
        )
        if existing:
            skipped += 1
            continue

        # Deterministic ID: hash only used for uniqueness, collision handled by INSERT IGNORE
        hash_str = f"{date_str}_{home}_{away}".encode('utf-8')
        game_id = 900000000 + int(hashlib.md5(hash_str).hexdigest(), 16) % 10_000_000

        # Determine round/season from date
        year = int(date_str[:4])
        month = int(date_str[5:7])
        # Season: use year for internationals
        season = year

        # Insert
        try:
            execute(
                """INSERT IGNORE INTO tm_games
                   (game_id, competition_id, season, round, date,
                    home_club_id, away_club_id,
                    home_club_goals, away_club_goals,
                    home_club_name, away_club_name)
                   VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s)""",
                [game_id, m["competition_id"], season, "", date_str,
                 m["home_goals"], m["away_goals"], home, away],
                db="football_pred"
            )
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error inserting {home} vs {away} ({date_str}): {e}")

        if (i + 1) % 1000 == 0:
            print(f"  Progress: {i+1}/{len(matches)} ({inserted} inserted)")

    print(f"  Done: {inserted} inserted, {skipped} skipped, {errors} errors")
    return inserted


def verify():
    """Verify the import by checking competition counts."""
    print("\n=== Verification: International matches in tm_games ===")
    rows = query(
        """SELECT competition_id, COUNT(*) as cnt,
                  MIN(date) as min_d, MAX(date) as max_d
           FROM tm_games
           WHERE competition_id IN ('FIWC','EURO','COPA','AFAC','AFCN',
                                    'WCQL','EUCON','AFQL','ACQL',
                                    'UNL','CNL','GC','OFC','FR')
           GROUP BY competition_id
           ORDER BY cnt DESC""",
        db="football_pred"
    )
    total = 0
    for r in rows:
        print(f"  {r['competition_id']:8s} {r['cnt']:>5} rows  {r['min_d']} -> {r['max_d']}")
        total += r['cnt']
    print(f"  Total: {total}")


def main():
    t0 = time.time()

    rows = download_data()
    matches = filter_and_map(rows)
    inserted = import_to_tm_games(matches)
    verify()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
