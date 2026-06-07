# -*- coding: utf-8 -*-
"""
Import international player appearances from Transfermarkt game_events.

Builds tm_appearances records from game_events.csv for international matches.
Extracts goals, assists, cards from event data.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from data.mysql_client import query, execute

DATA_DIR = os.getenv("TRANSFERMARKT_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data", "transfermarkt"))

# International competition_ids to process
INTL_COMPS = ['FIWC', 'EURO', 'AFAC', 'COPA', 'AFCN']


def get_international_game_ids():
    """Get game_ids for international matches from tm_games."""
    rows = query(
        "SELECT game_id, competition_id, date, home_club_name, away_club_name "
        "FROM tm_games WHERE competition_id IN ('FIWC','EURO','AFAC','COPA','AFCN')",
        db='football_pred'
    )
    return {r['game_id']: r for r in rows}


def load_events(game_ids):
    """Load game events for international matches from CSV."""
    print(f"Loading events for {len(game_ids)} international games...")
    
    chunk_iter = pd.read_csv(os.path.join(DATA_DIR, 'game_events.csv'), chunksize=100000)
    intl_events = []
    
    for chunk in chunk_iter:
        intl = chunk[chunk['game_id'].isin(game_ids)]
        if len(intl) > 0:
            intl_events.append(intl)
    
    if not intl_events:
        return pd.DataFrame()
    
    events = pd.concat(intl_events, ignore_index=True)
    print(f"  Loaded {len(events)} events")
    return events


def build_appearances(events, game_info):
    """Build appearance records from events."""
    appearances = {}
    
    for _, ev in events.iterrows():
        game_id = ev['game_id']
        player_id = ev['player_id']
        
        if pd.isna(player_id) or player_id == 0:
            continue
        
        player_id = int(player_id)
        key = (game_id, player_id)
        
        if key not in appearances:
            info = game_info.get(game_id, {})
            appearances[key] = {
                'game_id': game_id,
                'player_id': player_id,
                'competition_id': info.get('competition_id', ''),
                'goals': 0,
                'assists': 0,
                'yellow_cards': 0,
                'red_cards': 0,
                'minutes': 0,
                'event_count': 0,
            }
        
        app = appearances[key]
        app['event_count'] += 1
        
        ev_type = ev.get('type', '')
        
        if ev_type == 'Goals':
            app['goals'] += 1
            # Check for assist
            assist_id = ev.get('player_assist_id')
            if pd.notna(assist_id) and assist_id != 0:
                assist_key = (game_id, int(assist_id))
                if assist_key not in appearances:
                    info = game_info.get(game_id, {})
                    appearances[assist_key] = {
                        'game_id': game_id,
                        'player_id': int(assist_id),
                        'competition_id': info.get('competition_id', ''),
                        'goals': 0, 'assists': 0,
                        'yellow_cards': 0, 'red_cards': 0,
                        'minutes': 0, 'event_count': 0,
                    }
                appearances[assist_key]['assists'] += 1
        
        elif ev_type == 'Cards':
            desc = str(ev.get('description', ''))
            if 'Red' in desc or '2. Yellow' in desc:
                app['red_cards'] += 1
            else:
                app['yellow_cards'] += 1
        
        # Estimate minutes from substitution data
        elif ev_type == 'Substitutions':
            minute = ev.get('minute', 45)
            if pd.isna(minute):
                minute = 45
            player_in = ev.get('player_in_id')
            
            # Player going out played until this minute
            app['minutes'] = max(app['minutes'], int(minute))
            
            # Player coming in played from this minute to ~90
            if pd.notna(player_in) and player_in != 0:
                in_key = (game_id, int(player_in))
                if in_key not in appearances:
                    info = game_info.get(game_id, {})
                    appearances[in_key] = {
                        'game_id': game_id,
                        'player_id': int(player_in),
                        'competition_id': info.get('competition_id', ''),
                        'goals': 0, 'assists': 0,
                        'yellow_cards': 0, 'red_cards': 0,
                        'minutes': 0, 'event_count': 0,
                    }
                appearances[in_key]['minutes'] = max(
                    appearances[in_key]['minutes'], 90 - int(minute)
                )
    
    # For players with events but no substitution data, estimate minutes
    for key, app in appearances.items():
        if app['minutes'] == 0 and app['event_count'] > 0:
            # Player had events but wasn't substituted - likely played most of the game
            app['minutes'] = 90
    
    return appearances


def get_player_names(player_ids):
    """Get player names from tm_players."""
    if not player_ids:
        return {}
    
    placeholders = ','.join(['%s'] * len(player_ids))
    rows = query(
        f"SELECT player_id, name FROM tm_players WHERE player_id IN ({placeholders})",
        list(player_ids), db='football_pred'
    )
    return {r['player_id']: r['name'] for r in rows}


def import_appearances(appearances):
    """Import appearances into tm_appearances table."""
    print(f"\nImporting {len(appearances)} appearances...")
    
    # Get player names
    player_ids = set(app['player_id'] for app in appearances.values())
    player_names = get_player_names(player_ids)
    
    inserted = 0
    skipped = 0
    errors = 0
    
    for i, (key, app) in enumerate(appearances.items()):
        game_id = app['game_id']
        player_id = app['player_id']
        
        # Generate appearance_id
        appearance_id = f"intl_{game_id}_{player_id}"
        
        # Check if already exists
        existing = query(
            "SELECT appearance_id FROM tm_appearances WHERE appearance_id = %s",
            [appearance_id], db='football_pred'
        )
        if existing:
            skipped += 1
            continue
        
        player_name = player_names.get(player_id, '')
        
        try:
            execute(
                """INSERT IGNORE INTO tm_appearances
                   (appearance_id, game_id, player_id, player_name,
                    player_club_id, competition_id,
                    goals, assists, minutes_played, yellow_cards, red_cards)
                   VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s)""",
                [appearance_id, game_id, player_id, player_name,
                 app['competition_id'], app['goals'], app['assists'],
                 app['minutes'], app['yellow_cards'], app['red_cards']],
                db='football_pred'
            )
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error: {e}")
        
        if (i + 1) % 500 == 0:
            print(f"  Progress: {i+1}/{len(appearances)} ({inserted} inserted)")
    
    print(f"  Done: {inserted} inserted, {skipped} skipped, {errors} errors")
    return inserted


def verify():
    """Verify the import."""
    print("\n=== Verification ===")
    
    # Count international appearances
    rows = query(
        """SELECT competition_id, COUNT(*) as cnt,
                  SUM(goals) as total_goals, SUM(assists) as total_assists
           FROM tm_appearances
           WHERE competition_id IN ('FIWC','EURO','AFAC','COPA','AFCN')
           GROUP BY competition_id""",
        db='football_pred'
    )
    
    total = 0
    for r in rows:
        print(f"  {r['competition_id']:8s} {r['cnt']:>5} apps  "
              f"{r['total_goals']} goals  {r['total_assists']} assists")
        total += r['cnt']
    print(f"  Total: {total} international appearances")
    
    # Sample some appearances
    rows2 = query(
        """SELECT a.player_name, a.competition_id, a.goals, a.assists,
                  a.minutes_played, a.yellow_cards, a.red_cards
           FROM tm_appearances a
           WHERE a.competition_id IN ('FIWC','EURO','AFAC','COPA','AFCN')
             AND a.goals > 0
           ORDER BY a.goals DESC LIMIT 10""",
        db='football_pred'
    )
    
    print("\n=== Top scorers ===")
    for r in rows2:
        print(f"  {r['player_name']:25s} {r['competition_id']:6s} "
              f"{r['goals']}G {r['assists']}A {r['minutes_played']}min")


def main():
    t0 = time.time()
    
    # Get international game info
    game_info = get_international_game_ids()
    print(f"Found {len(game_info)} international games in tm_games")
    
    # Load events
    events = load_events(set(game_info.keys()))
    if events.empty:
        print("No events found")
        return
    
    # Build appearances
    appearances = build_appearances(events, game_info)
    print(f"Built {len(appearances)} appearance records")
    
    # Import
    import_appearances(appearances)
    
    # Verify
    verify()
    
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
