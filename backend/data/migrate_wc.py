"""
Update WC 2026 database with real data from FIFA API.
Fetched from: https://cxm-api.fifa.com/fifaplusweb/api/sections/teamsModule/...
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import mysql.connector
from backend.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS

DB = "football_pred"

# Real FIFA data - 48 teams with official group assignments
# Source: FIFA+ API (seasonId=285023)
TEAMS = [
    # (fifa_team_id, team_name, confederation, fifa_ranking, group, appearances, is_host)
    ("43911", "Mexico",                "CONCACAF",  15, "A",  18, True),
    ("43995", "Czechia",               "UEFA",      41, "A",   2, False),
    ("43822", "Korea Republic",        "AFC",       25, "A",  11, False),
    ("43883", "South Africa",          "CAF",       60, "A",   4, False),

    ("43899", "Canada",                "CONCACAF",  30, "B",   2, True),
    ("44037", "Bosnia and Herzegovina","UEFA",      65, "B",   1, False),
    ("43834", "Qatar",                 "AFC",       55, "B",   2, False),
    ("43971", "Switzerland",           "UEFA",      19, "B",  12, False),

    ("43924", "Brazil",                "CONMEBOL",   6, "C",  23, False),
    ("43908", "Haiti",                 "CONCACAF",  83, "C",   2, False),
    ("43872", "Morocco",               "CAF",        8, "C",   7, False),
    ("43967", "Scotland",              "UEFA",      43, "C",   9, False),

    ("43921", "USA",                   "CONCACAF",  16, "D",  12, True),
    ("43976", "Australia",             "AFC",       27, "D",   7, False),
    ("43928", "Paraguay",              "CONMEBOL",  40, "D",   9, False),
    ("43972", "Turkiye",               "UEFA",      22, "D",   3, False),

    ("43854", "Cote d'Ivoire",         "CAF",       34, "E",   4, False),
    ("1895293","Curacao",              "CONCACAF",  82, "E",   1, False),
    ("43927", "Ecuador",               "CONMEBOL",  23, "E",   4, False),
    ("43948", "Germany",               "UEFA",      10, "E",  21, False),

    ("43819", "Japan",                 "AFC",       18, "F",   8, False),
    ("43960", "Netherlands",           "UEFA",       7, "F",  12, False),
    ("43970", "Sweden",                "UEFA",      38, "F",  12, False),
    ("43888", "Tunisia",               "CAF",       44, "F",   7, False),

    ("43935", "Belgium",               "UEFA",       9, "G",  14, False),
    ("43855", "Egypt",                 "CAF",       29, "G",   4, False),
    ("43817", "IR Iran",               "AFC",       21, "G",   7, False),
    ("43978", "New Zealand",           "OFC",       85, "G",   3, False),

    ("43850", "Cabo Verde",            "CAF",       69, "H",   1, False),
    ("43835", "Saudi Arabia",          "AFC",       61, "H",   7, False),
    ("43969", "Spain",                 "UEFA",       2, "H",  17, False),
    ("43930", "Uruguay",               "CONMEBOL",  17, "H",  14, False),

    ("43946", "France",                "UEFA",       1, "I",  17, False),
    ("43818", "Iraq",                  "AFC",       57, "I",   2, False),
    ("43961", "Norway",                "UEFA",      31, "I",   4, False),
    ("43879", "Senegal",               "CAF",       14, "I",   4, False),

    ("43843", "Algeria",               "CAF",       28, "J",   5, False),
    ("43922", "Argentina",             "CONMEBOL",   3, "J",  18, False),
    ("43934", "Austria",               "UEFA",      24, "J",   8, False),
    ("43820", "Jordan",                "AFC",       63, "J",   1, False),

    ("43926", "Colombia",              "CONMEBOL",  13, "K",   7, False),
    ("20014", "Congo DR",              "CAF",       46, "K",   2, False),
    ("43963", "Portugal",              "UEFA",       5, "K",   9, False),
    ("44005", "Uzbekistan",            "AFC",       50, "K",   1, False),

    ("43938", "Croatia",               "UEFA",      11, "L",   7, False),
    ("43942", "England",               "UEFA",       4, "L",  17, False),
    ("43860", "Ghana",                 "CAF",       74, "L",   4, False),
    ("43914", "Panama",                "CONCACAF",  33, "L",   2, False),
]

# Elo estimates based on FIFA ranking
def ranking_to_elo(ranking):
    """Approximate Elo from FIFA ranking."""
    if ranking <= 5:
        return 1850 + (5 - ranking) * 15
    elif ranking <= 10:
        return 1780 + (10 - ranking) * 14
    elif ranking <= 20:
        return 1700 + (20 - ranking) * 8
    elif ranking <= 30:
        return 1620 + (30 - ranking) * 8
    elif ranking <= 50:
        return 1520 + (50 - ranking) * 5
    elif ranking <= 70:
        return 1420 + (70 - ranking) * 5
    else:
        return 1300 + max(0, (100 - ranking) * 3)


# Group stage schedule (same as before)
GROUP_MATCH_SCHEDULE = [
    (1, 0, 3),  # Matchday 1: Team[0] vs Team[3]
    (1, 1, 2),  # Matchday 1: Team[1] vs Team[2]
    (2, 0, 2),  # Matchday 2: Team[0] vs Team[2]
    (2, 1, 3),  # Matchday 2: Team[1] vs Team[3]
    (3, 0, 1),  # Matchday 3: Team[0] vs Team[1]
    (3, 2, 3),  # Matchday 3: Team[2] vs Team[3]
]

GROUP_MATCHDATES = {
    1: "2026-06-11",
    2: "2026-06-17",
    3: "2026-06-23",
}


def get_conn():
    return mysql.connector.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=DB, charset="utf8mb4",
    )


def update_tables(conn):
    """Update wc_groups with real FIFA data."""
    cur = conn.cursor()

    # Add fifa_team_id column if not exists
    try:
        cur.execute("ALTER TABLE wc_groups ADD COLUMN fifa_team_id VARCHAR(20) DEFAULT ''")
        conn.commit()
    except mysql.connector.errors.OperationalError:
        pass  # column already exists

    # Add appearances column if not exists
    try:
        cur.execute("ALTER TABLE wc_groups ADD COLUMN appearances INT DEFAULT 0")
        conn.commit()
    except mysql.connector.errors.OperationalError:
        pass

    # Add is_host column if not exists
    try:
        cur.execute("ALTER TABLE wc_groups ADD COLUMN is_host TINYINT DEFAULT 0")
        conn.commit()
    except mysql.connector.errors.OperationalError:
        pass

    # Create tables if not exist (idempotent)
    cur.execute("""CREATE TABLE IF NOT EXISTS wc_groups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_name VARCHAR(5) NOT NULL,
        team VARCHAR(100) NOT NULL,
        confederation VARCHAR(20) DEFAULT '',
        fifa_ranking INT DEFAULT 0,
        elo_rating FLOAT DEFAULT 1500,
        pot INT DEFAULT 0,
        fifa_team_id VARCHAR(20) DEFAULT '',
        appearances INT DEFAULT 0,
        is_host TINYINT DEFAULT 0,
        UNIQUE KEY uk_group_team (group_name, team)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wc_standings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        group_name VARCHAR(5) NOT NULL,
        team VARCHAR(100) NOT NULL,
        played INT DEFAULT 0,
        wins INT DEFAULT 0,
        draws INT DEFAULT 0,
        losses INT DEFAULT 0,
        goals_for INT DEFAULT 0,
        goals_against INT DEFAULT 0,
        goal_diff INT DEFAULT 0,
        points INT DEFAULT 0,
        position INT DEFAULT 0,
        UNIQUE KEY uk_standing_team (group_name, team)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    conn.commit()

    # Clear and repopulate
    cur.execute("DELETE FROM wc_groups")
    cur.execute("DELETE FROM wc_standings")

    for fifa_id, name, conf, rank, group, apps, is_host in TEAMS:
        elo = ranking_to_elo(rank)
        cur.execute(
            """INSERT INTO wc_groups
               (group_name, team, confederation, fifa_ranking, elo_rating, pot,
                fifa_team_id, appearances, is_host)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [group, name, conf, rank, elo, 0, fifa_id, apps, 1 if is_host else 0]
        )
        cur.execute(
            """INSERT INTO wc_standings
               (group_name, team, played, wins, draws, losses,
                goals_for, goals_against, goal_diff, points, position)
               VALUES (%s, %s, 0, 0, 0, 0, 0, 0, 0, 0, 0)""",
            [group, name]
        )

    conn.commit()
    cur.close()
    print(f"[WC] Updated {len(TEAMS)} teams with real FIFA data")


def rebuild_group_matches(conn):
    """Rebuild group stage fixtures with correct team assignments."""
    cur = conn.cursor()

    # Delete old WC2026 fixtures
    cur.execute("DELETE FROM fixtures WHERE league_code='WC2026'")
    conn.commit()

    # Get teams by group (ordered by pot/fifa_ranking)
    cur.execute(
        "SELECT group_name, team, fifa_ranking FROM wc_groups ORDER BY group_name, fifa_ranking"
    )
    rows = cur.fetchall()

    groups = {}
    for row in rows:
        g = row[0]
        if g not in groups:
            groups[g] = []
        groups[g].append(row[1])

    # Insert group stage matches
    match_count = 0
    for group_name in sorted(groups.keys()):
        g = groups[group_name]
        for matchday, idx_a, idx_b in GROUP_MATCH_SCHEDULE:
            home_team = g[idx_a]
            away_team = g[idx_b]
            match_date = GROUP_MATCHDATES.get(matchday, "2026-06-11")

            cur.execute(
                """INSERT INTO fixtures
                   (league_code, season, match_date, home_team, away_team, status, source)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                ["WC2026", "2026", match_date, home_team, away_team, "scheduled", "fifa_api"]
            )
            match_count += 1

    conn.commit()
    cur.close()
    print(f"[WC] Rebuilt {match_count} group stage fixtures")


def print_summary(conn):
    """Print final summary."""
    cur = conn.cursor(dictionary=True)

    cur.execute(
        "SELECT group_name, team, confederation, fifa_ranking, elo_rating, appearances, is_host "
        "FROM wc_groups ORDER BY group_name, fifa_ranking"
    )
    rows = cur.fetchall()

    current_group = None
    for r in rows:
        if r['group_name'] != current_group:
            if current_group:
                print()
            current_group = r['group_name']
            print(f"Group {current_group}:")
        host_tag = " (HOST)" if r['is_host'] else ""
        print(f"  {r['team']:25s} {r['confederation']:8s} FIFA #{r['fifa_ranking']:>3}  "
              f"Elo {r['elo_rating']:.0f}  WC apps: {r['appearances']}{host_tag}")

    cur.execute("SELECT COUNT(*) as cnt FROM fixtures WHERE league_code='WC2026'")
    cnt = cur.fetchone()['cnt']
    print(f"\nTotal WC2026 fixtures: {cnt}")

    cur.execute("SELECT COUNT(*) as cnt FROM wc_groups")
    cnt = cur.fetchone()['cnt']
    print(f"Total teams in wc_groups: {cnt}")

    cur.close()


def main():
    print("=" * 60)
    print("WC 2026 - Update with real FIFA API data")
    print("=" * 60)
    print("Source: https://cxm-api.fifa.com/fifaplusweb/api/sections/teamsModule/")
    print()

    conn = get_conn()
    try:
        update_tables(conn)
        rebuild_group_matches(conn)
        print()
        print_summary(conn)
        print("\n[WC] Database updated with real FIFA data!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
