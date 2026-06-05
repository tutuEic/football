"""Ad-hoc fixtures query script. Run directly, not imported."""
import os
import mysql.connector

def main():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASS", ""),
        database=os.getenv("MYSQL_DB_PRED", "football_pred"),
    )
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM fixtures WHERE DATE(match_date) = CURDATE()")
    today = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM fixtures WHERE DATE(match_date) >= CURDATE() AND DATE(match_date) < DATE_ADD(CURDATE(), INTERVAL 3 DAY)")
    up3 = c.fetchone()[0]

    c.execute("SELECT DATE(match_date) d, COUNT(*) cnt FROM fixtures WHERE DATE(match_date) >= CURDATE() AND DATE(match_date) < DATE_ADD(CURDATE(), INTERVAL 3 DAY) GROUP BY DATE(match_date) ORDER BY d")
    brk = c.fetchall()

    c.execute("SELECT league_code, COUNT(*) cnt FROM fixtures WHERE DATE(match_date) = CURDATE() GROUP BY league_code ORDER BY cnt DESC")
    lg = c.fetchall()

    c.execute("SELECT COUNT(*), COUNT(DISTINCT league_code) FROM fixtures")
    t, lc = c.fetchone()

    c.execute("SELECT id, records_affected, status, finished_at FROM data_refresh_log ORDER BY id DESC LIMIT 3")
    log = c.fetchall()

    conn.close()

    print(f"TODAY={today}")
    print(f"NEXT3={up3}")
    print(f"TOTAL={t}|LEAGUES={lc}")
    print(f"BREAKDOWN={brk}")
    print(f"LEAGUES_TODAY={lg}")
    print(f"PIPELINE_LOG={log}")

if __name__ == "__main__":
    main()
