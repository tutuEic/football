"""Check tm_games structure for active player filtering."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from data.mysql_client import get_connection

conn = get_connection(db="football_pred")
cur = conn.cursor(dictionary=True)

cur.execute('DESCRIBE tm_games')
print('tm_games columns:')
for r in cur.fetchall():
    print(f"  {r['Field']:25s} {r['Type']}")

cur.execute('SELECT * FROM tm_games LIMIT 2')
rows = cur.fetchall()
print('\nSample rows:')
for r in rows:
    print(f"  {r}")

# Check date range
cur.execute('SELECT MIN(date) as earliest, MAX(date) as latest FROM tm_games')
print('\nDate range:', cur.fetchone())

# Check how many players have recent appearances (2024+)
cur.execute("""
    SELECT COUNT(DISTINCT a.player_id) as cnt
    FROM tm_appearances a
    JOIN tm_games g ON a.game_id = g.game_id
    WHERE g.date >= '2024-01-01'
""")
print('\nPlayers with 2024+ appearances:', cur.fetchone())

conn.close()
