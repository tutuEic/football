# -*- coding: utf-8 -*-
"""Fix tm_clubs.total_market_value and squad_size from actual tm_players data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query, execute

def fix_club_stats():
    """Recalculate total_market_value and squad_size from tm_players."""
    clubs = query("SELECT club_id FROM tm_clubs", db="football_pred")
    updated = 0
    for c in clubs:
        cid = c["club_id"]
        stats = query("""
            SELECT COUNT(*) as cnt, 
                   COALESCE(SUM(market_value_in_eur), 0) as total_mv
            FROM tm_players WHERE current_club_id = %s
        """, [cid], db="football_pred")
        if stats and stats[0]["cnt"] > 0:
            cnt = stats[0]["cnt"]
            mv = int(stats[0]["total_mv"])
            execute("""
                UPDATE tm_clubs SET squad_size = %s, total_market_value = %s
                WHERE club_id = %s
            """, [cnt, mv, cid], db="football_pred")
            updated += 1
    print(f"Updated {updated} clubs")

if __name__ == "__main__":
    fix_club_stats()
