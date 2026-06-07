"""
Insert 2026 FIFA World Cup official squad data into MySQL.
Data scraped from Wikipedia: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads
Run on Windows: python insert_squads.py
"""
import json
import mysql.connector
import os

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'football_pred',
    'charset': 'utf8mb4',
    'use_unicode': True,
}

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wc_squads_data.json')

def main():
    # Load data
    print(f"Loading squad data from {DATA_FILE}...")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        squads_data = json.load(f)
    print(f"Loaded {len(squads_data)} player records")
    
    print("Connecting to MySQL...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Create table
    print("Creating wc_official_squads table...")
    cursor.execute("DROP TABLE IF EXISTS wc_official_squads")
    cursor.execute("""
        CREATE TABLE wc_official_squads (
            id INT AUTO_INCREMENT PRIMARY KEY,
            team_name VARCHAR(100) NOT NULL,
            player_name VARCHAR(200) NOT NULL,
            position VARCHAR(50) NOT NULL,
            club VARCHAR(200),
            jersey_number INT,
            INDEX idx_team (team_name),
            INDEX idx_position (position)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    
    # Insert data
    print(f"Inserting {len(squads_data)} player records...")
    insert_sql = """
        INSERT INTO wc_official_squads (team_name, player_name, position, club, jersey_number)
        VALUES (%s, %s, %s, %s, %s)
    """
    
    batch = []
    for rec in squads_data:
        batch.append((
            rec['team_name'],
            rec['player_name'],
            rec['position'],
            rec['club'],
            rec['jersey_number']
        ))
    
    cursor.executemany(insert_sql, batch)
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM wc_official_squads")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT team_name) FROM wc_official_squads")
    teams = cursor.fetchone()[0]
    
    cursor.execute("SELECT team_name, COUNT(*) as cnt FROM wc_official_squads GROUP BY team_name ORDER BY team_name")
    team_counts = cursor.fetchall()
    
    print(f"\n=== RESULTS ===")
    print(f"Total players inserted: {total}")
    print(f"Total teams: {teams}")
    print(f"\nPer-team breakdown:")
    for team, cnt in team_counts:
        print(f"  {team}: {cnt} players")
    
    # Show position distribution
    cursor.execute("SELECT position, COUNT(*) as cnt FROM wc_official_squads GROUP BY position ORDER BY cnt DESC")
    pos_counts = cursor.fetchall()
    print(f"\nPosition distribution:")
    for pos, cnt in pos_counts:
        print(f"  {pos}: {cnt}")
    
    cursor.close()
    conn.close()
    print("\nDone!")

if __name__ == '__main__':
    main()
