import os
import mysql.connector
from datetime import date, timedelta

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASS", ""),
    database=os.getenv("MYSQL_DB_PRED", "football_pred"),
    charset="utf8mb4",
)
cur = conn.cursor(buffered=True)

today = date.today()

for i in range(1, 15):
    d = today + timedelta(days=i)
    cur.execute("SELECT COUNT(*), league_code FROM fixtures WHERE match_date = %s AND season = '2526' GROUP BY league_code", (d,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {d}: {r[0]} ({r[1]})")

cur.execute("SELECT DISTINCT season FROM fixtures ORDER BY season")
print("\nAll seasons:", [r[0] for r in cur.fetchall()])

cur.execute("""
    SELECT league_code, match_date, COUNT(*)
    FROM fixtures
    WHERE season = '2526' AND match_date >= '2026-05-20'
    GROUP BY league_code, match_date
    ORDER BY match_date DESC, league_code
""")
print("\nRecent matches by league+date:")
for row in cur.fetchall():
    print(f"  {row[0]:6s} {row[1]} : {row[2]}")

cur.close()
conn.close()
