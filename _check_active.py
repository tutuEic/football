"""Check tm_games structure for active player filtering."""
import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1', port=3306, user='root', password='123456',
    database='football_pred', charset='utf8mb4'
)
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
