"""
实时数据表结构 — fixtures, live_matches, match_stats
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.mysql_client import get_connection

DB = "football_pred"

def get_conn():
    return get_connection(db=DB)

def create_tables():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Fixtures — upcoming/daily matches
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fixtures (
        id INT AUTO_INCREMENT PRIMARY KEY,
        league_code VARCHAR(10) NOT NULL,
        season VARCHAR(10) NOT NULL,
        match_date DATE NOT NULL,
        match_time VARCHAR(10),
        home_team VARCHAR(100) NOT NULL,
        away_team VARCHAR(100) NOT NULL,
        home_team_id INT,
        away_team_id INT,
        status VARCHAR(20) DEFAULT 'scheduled',
        home_score INT,
        away_score INT,
        minute INT DEFAULT 0,
        winner VARCHAR(10),
        odds_home DECIMAL(6,2),
        odds_draw DECIMAL(6,2),
        odds_away DECIMAL(6,2),
        odds_over25 DECIMAL(6,2),
        odds_under25 DECIMAL(6,2),
        source VARCHAR(50) DEFAULT 'football-data.co.uk',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_match (league_code, season, home_team, away_team, match_date),
        INDEX idx_date (match_date),
        INDEX idx_league_date (league_code, match_date),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 2. Live matches — in-play data (minute-by-minute during matches)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS live_matches (
        id INT AUTO_INCREMENT PRIMARY KEY,
        fixture_id INT NOT NULL,
        home_score INT DEFAULT 0,
        away_score INT DEFAULT 0,
        minute INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'live',
        home_shots INT DEFAULT 0,
        away_shots INT DEFAULT 0,
        home_shots_on_target INT DEFAULT 0,
        away_shots_on_target INT DEFAULT 0,
        home_possession DECIMAL(5,1) DEFAULT 50.0,
        away_possession DECIMAL(5,1) DEFAULT 50.0,
        home_corners INT DEFAULT 0,
        away_corners INT DEFAULT 0,
        home_yellow_cards INT DEFAULT 0,
        away_yellow_cards INT DEFAULT 0,
        home_red_cards INT DEFAULT 0,
        away_red_cards INT DEFAULT 0,
        home_dangerous_attacks INT DEFAULT 0,
        away_dangerous_attacks INT DEFAULT 0,
        events_json TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_fixture (fixture_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 3. Match stats — post-match advanced stats (FBref)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS match_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        fixture_id INT,
        match_id INT,
        home_xg DECIMAL(6,3),
        away_xg DECIMAL(6,3),
        home_npxg DECIMAL(6,3),
        away_npxg DECIMAL(6,3),
        home_shots INT,
        away_shots INT,
        home_shots_on_target INT,
        away_shots_on_target INT,
        home_possession DECIMAL(5,1),
        away_possession DECIMAL(5,1),
        home_passes INT,
        away_passes INT,
        home_pass_accuracy DECIMAL(5,1),
        away_pass_accuracy DECIMAL(5,1),
        home_fouls INT,
        away_fouls INT,
        home_corners INT,
        away_corners INT,
        home_yellow INT,
        away_yellow INT,
        home_red INT,
        away_red INT,
        home_ppda DECIMAL(6,2),
        away_ppda DECIMAL(6,2),
        attendance INT,
        referee VARCHAR(100),
        source VARCHAR(50) DEFAULT 'fbref',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_fixture (fixture_id),
        INDEX idx_match (match_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 4. Data refresh log
    cur.execute("""
    CREATE TABLE IF NOT EXISTS data_refresh_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        source VARCHAR(50) NOT NULL,
        action VARCHAR(50) NOT NULL,
        records_affected INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'ok',
        error_message TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("All tables created successfully.")

if __name__ == "__main__":
    create_tables()
