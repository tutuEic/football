"""
Transfermarkt 数据导入管线 (v2 — 修复 NaN 处理)
"""
import mysql.connector
import pandas as pd
import numpy as np
import sys, os, time

DATA_DIR = r"D:\xiaoli\data\transfermarkt"
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASS", ""),
    "database": os.getenv("MYSQL_DB_PRED", "football_pred"),
    "charset": "utf8mb4",
    "allow_local_infile": True,
}

def get_conn():
    return mysql.connector.connect(**DB_CONFIG)

def safe_int(val, default=0):
    if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "NaT"): return default
    try: return int(float(val))
    except: return default

def safe_float(val, default=0.0):
    if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "NaT"): return default
    try: return float(val)
    except: return default

def safe_str(val, default=""):
    if pd.isna(val) or val is None: return default
    return str(val)

def create_tables():
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tm_clubs (
        club_id INT PRIMARY KEY, name VARCHAR(200),
        domestic_competition_id VARCHAR(10), total_market_value BIGINT,
        squad_size INT, average_age DECIMAL(5,2),
        foreigners_number INT, national_team_players INT,
        stadium_name VARCHAR(200), stadium_seats INT,
        coach_name VARCHAR(200), last_season INT
    ) ENGINE=InnoDB""")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tm_players (
        player_id INT PRIMARY KEY, name VARCHAR(200),
        first_name VARCHAR(100), last_name VARCHAR(100),
        current_club_id INT, current_club_name VARCHAR(200),
        position VARCHAR(50), sub_position VARCHAR(50),
        foot VARCHAR(10), height_in_cm INT, date_of_birth DATE,
        country_of_citizenship VARCHAR(100),
        market_value_in_eur BIGINT, highest_market_value_in_eur BIGINT,
        INDEX idx_club (current_club_id), INDEX idx_name (name(50))
    ) ENGINE=InnoDB""")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tm_games (
        game_id INT PRIMARY KEY, competition_id VARCHAR(20),
        season INT, round VARCHAR(50), date DATE,
        home_club_id INT, away_club_id INT,
        home_club_goals INT, away_club_goals INT,
        home_club_name VARCHAR(200), away_club_name VARCHAR(200),
        home_club_formation VARCHAR(20), away_club_formation VARCHAR(20),
        stadium VARCHAR(200), attendance INT,
        INDEX idx_home (home_club_id), INDEX idx_away (away_club_id)
    ) ENGINE=InnoDB""")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tm_appearances (
        appearance_id VARCHAR(50) PRIMARY KEY,
        game_id INT, player_id INT, player_name VARCHAR(200),
        player_club_id INT, competition_id VARCHAR(20),
        goals INT DEFAULT 0, assists INT DEFAULT 0,
        minutes_played INT DEFAULT 0, yellow_cards INT DEFAULT 0, red_cards INT DEFAULT 0,
        INDEX idx_player (player_id), INDEX idx_game (game_id)
    ) ENGINE=InnoDB""")
    
    conn.commit()
    cur.close(); conn.close()
    print("Tables ready.")


def import_clubs():
    print("Importing clubs...")
    df = pd.read_csv(os.path.join(DATA_DIR, "clubs.csv"))
    conn = get_conn(); cur = conn.cursor()
    for _, r in df.iterrows():
        cur.execute("""INSERT IGNORE INTO tm_clubs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
            safe_int(r["club_id"]), safe_str(r["name"]),
            safe_str(r.get("domestic_competition_id")), safe_int(r.get("total_market_value")),
            safe_int(r.get("squad_size")), safe_float(r.get("average_age")),
            safe_int(r.get("foreigners_number")), safe_int(r.get("national_team_players")),
            safe_str(r.get("stadium_name")), safe_int(r.get("stadium_seats")),
            safe_str(r.get("coach_name")), safe_int(r.get("last_season")),
        ))
    conn.commit(); cur.close(); conn.close()
    print(f"  {len(df)} clubs.")


def import_players():
    print("Importing players...")
    df = pd.read_csv(os.path.join(DATA_DIR, "players.csv"))
    conn = get_conn(); cur = conn.cursor(); count = 0
    for _, r in df.iterrows():
        dob = r.get("date_of_birth")
        dob = None if pd.isna(dob) or str(dob).strip() in ("", "nan", "NaT") else str(dob)[:10]
        cur.execute("""INSERT IGNORE INTO tm_players VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
            safe_int(r["player_id"]), safe_str(r.get("name")),
            safe_str(r.get("first_name")), safe_str(r.get("last_name")),
            safe_int(r.get("current_club_id")), safe_str(r.get("current_club_name")),
            safe_str(r.get("position")), safe_str(r.get("sub_position")),
            safe_str(r.get("foot")), safe_int(r.get("height_in_cm")),
            dob, safe_str(r.get("country_of_citizenship")),
            safe_int(r.get("market_value_in_eur")), safe_int(r.get("highest_market_value_in_eur")),
        ))
        count += 1
        if count % 10000 == 0: conn.commit(); print(f"  {count}/{len(df)}...")
    conn.commit(); cur.close(); conn.close()
    print(f"  {count} players.")


def import_games():
    print("Importing games...")
    df = pd.read_csv(os.path.join(DATA_DIR, "games.csv"))
    conn = get_conn(); cur = conn.cursor(); count = 0
    for _, r in df.iterrows():
        date_val = r.get("date")
        date_val = None if pd.isna(date_val) or str(date_val).strip() in ("", "nan", "NaT") else str(date_val)[:10]
        cur.execute("""INSERT IGNORE INTO tm_games VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
            safe_int(r["game_id"]), safe_str(r.get("competition_id")),
            safe_int(r.get("season")), safe_str(r.get("round")),
            date_val, safe_int(r.get("home_club_id")), safe_int(r.get("away_club_id")),
            safe_int(r.get("home_club_goals")), safe_int(r.get("away_club_goals")),
            safe_str(r.get("home_club_name")), safe_str(r.get("away_club_name")),
            safe_str(r.get("home_club_formation")), safe_str(r.get("away_club_formation")),
            safe_str(r.get("stadium")), safe_int(r.get("attendance")),
        ))
        count += 1
        if count % 20000 == 0: conn.commit(); print(f"  {count}/{len(df)}...")
    conn.commit(); cur.close(); conn.close()
    print(f"  {count} games.")


def import_appearances():
    print("Importing appearances (~1.88M rows)...")
    conn = get_conn(); cur = conn.cursor(); total = 0
    for chunk in pd.read_csv(os.path.join(DATA_DIR, "appearances.csv"), chunksize=50000):
        for _, r in chunk.iterrows():
            cur.execute("""INSERT IGNORE INTO tm_appearances VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
                safe_str(r.get("appearance_id"), ""), safe_int(r.get("game_id")),
                safe_int(r.get("player_id")), safe_str(r.get("player_name")),
                safe_int(r.get("player_club_id")), safe_str(r.get("competition_id")),
                safe_int(r.get("goals")), safe_int(r.get("assists")),
                safe_int(r.get("minutes_played")), safe_int(r.get("yellow_cards")), safe_int(r.get("red_cards")),
            ))
        conn.commit(); total += len(chunk)
        print(f"  {total}/1884052...")
    cur.close(); conn.close()
    print(f"  {total} appearances.")


def verify():
    conn = get_conn(); cur = conn.cursor()
    for t in ["tm_clubs","tm_players","tm_games","tm_appearances"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {cur.fetchone()[0]:,}")
    cur.close(); conn.close()


if __name__ == "__main__":
    t0 = time.time()
    create_tables()
    import_clubs()
    import_players()
    import_games()
    import_appearances()
    verify()
    print(f"\nDone in {time.time()-t0:.0f}s")
