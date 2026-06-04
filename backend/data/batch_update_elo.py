# -*- coding: utf-8 -*-
"""
Batch update player Elo ratings in tm_players table.

Computes league_elo, intl_elo, elo_rating for all players
with enough appearances, then writes to database.
"""
import sys
import os
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query, execute
from engine.wc_player_elo import (
    load_player_appearances, load_player_metadata,
    calculate_player_elo, MIN_APPEARANCES, START_DATE
)
from collections import defaultdict


def batch_update_elo(batch_size=500):
    """Compute and write Elo for all qualified players."""
    print("=" * 60)
    print("Batch Player Elo Update")
    print("=" * 60)
    print(f"Start date: {START_DATE}")
    print(f"Min appearances: {MIN_APPEARANCES}")
    print()

    # Step 1: Load all appearances
    print("Loading all appearances ...")
    t0 = time.time()
    all_appearances = load_player_appearances()
    print(f"  Loaded {len(all_appearances)} appearance records in {time.time()-t0:.1f}s")

    # Group by player
    player_apps = defaultdict(list)
    for app in all_appearances:
        player_apps[app['player_id']].append(app)

    # Filter qualified
    qualified = {pid: apps for pid, apps in player_apps.items()
                 if len(apps) >= MIN_APPEARANCES}
    print(f"  Qualified players: {len(qualified)} (from {len(player_apps)} total)")

    # Step 2: Load metadata in batches
    print("Loading player metadata ...")
    player_ids = list(qualified.keys())
    metadata = {}
    for i in range(0, len(player_ids), 1000):
        batch = player_ids[i:i+1000]
        meta = load_player_metadata(batch)
        metadata.update(meta)
    print(f"  Loaded metadata for {len(metadata)} players")

    # Step 3: Compute Elo for each player
    print("Computing Elo ratings ...")
    updates = []
    now = date.today().isoformat()

    for i, (pid, apps) in enumerate(qualified.items()):
        meta = metadata.get(pid)
        elo_data = calculate_player_elo(pid, apps, meta)
        if elo_data:
            updates.append((
                elo_data['elo'],
                elo_data['league_elo'],
                elo_data['intl_elo'],
                now,
                pid,
            ))

        if (i + 1) % 2000 == 0:
            print(f"  {i+1}/{len(qualified)} computed")

    print(f"  Total: {len(updates)} players with Elo")

    # Step 4: Write to database
    print("Writing to database ...")
    conn = None
    try:
        import mysql.connector
        from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASS,
            database='football_pred', charset='utf8mb4'
        )
        cur = conn.cursor()

        sql = """UPDATE tm_players
                 SET elo_rating = %s, league_elo = %s, intl_elo = %s,
                     elo_updated_at = %s
                 WHERE player_id = %s"""

        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            cur.executemany(sql, batch)
            conn.commit()
            print(f"  {i+len(batch)}/{len(updates)} written")

        cur.close()
    finally:
        if conn:
            conn.close()

    print(f"\nDone! {len(updates)} players updated in {time.time()-t0:.1f}s")


if __name__ == '__main__':
    batch_update_elo()
