# -*- coding: utf-8 -*-
"""
World Cup Player Elo Rating System
===================================
Combines league and international match data to produce a comprehensive
player Elo rating for World Cup prediction.

Features:
- 4-year lookback (2022-2026) with recency decay
- Competition quality weighting (CL > Top leagues > Qualifiers > Friendlies)
- Position-aware scoring (GK/DF/MF/FW have different expectations)
- Separate league/international performance tracking
- Per-90 minute statistics
"""
import math
import sys
import os
from datetime import date, datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query

# ============================================================
# Configuration
# ============================================================

# Time window
LOOKBACK_YEARS = 4
START_DATE = "2022-01-01"

# Competition quality weights (0.0 - 1.0)
COMPETITION_WEIGHT = {
    # Elite club competitions
    "CL":    1.00,   # Champions League
    "EL":    0.85,   # Europa League
    "ECLQ":  0.75,   # Conference League qualifiers
    "CLQ":   0.70,   # Champions League qualifiers
    "ELQ":   0.70,   # Europa League qualifiers
    
    # Top 5 leagues
    "GB1":   0.90,   # Premier League
    "ES1":   0.90,   # La Liga
    "L1":    0.88,   # Bundesliga
    "IT1":   0.88,   # Serie A
    "FR1":   0.85,   # Ligue 1
    
    # Strong leagues
    "NL1":   0.75,   # Eredivisie
    "PO1":   0.75,   # Liga Portugal
    "BE1":   0.70,   # Belgian Pro League
    "TR1":   0.70,   # Super Lig
    "SC1":   0.68,   # Scottish Premiership
    "DK1":   0.65,   # Danish Superliga
    "GR1":   0.65,   # Greek Super League
    "RU1":   0.65,   # Russian Premier League
    "UKR1":  0.65,   # Ukrainian Premier League
    "A1":    0.65,   # Austrian Bundesliga
    "CH1":   0.65,   # Swiss Super League
    "SE1":   0.60,   # Swedish Allsvenskan
    "NO1":   0.60,   # Norwegian Eliteserien
    "RO1":   0.58,   # Romanian Liga I
    "SER1":  0.58,   # Serbian SuperLiga
    "HR1":   0.58,   # Croatian HNL
    
    # Medium leagues
    "GB2":   0.60,   # Championship
    "ES2":   0.60,   # La Liga 2
    "D2":    0.60,   # 2. Bundesliga
    "I2":    0.60,   # Serie B
    "F2":    0.58,   # Ligue 2
    
    # Non-European leagues
    "MLS1":  0.60,   # MLS
    "JAP1":  0.60,   # J1 League
    "KR1":   0.58,   # K League
    "SA1":   0.58,   # Saudi Pro League
    "BRA1":  0.65,   # Brasileirao
    "ARG1":  0.65,   # Argentine Primera
    "MEX1":  0.60,   # Liga MX
    "AUS1":  0.55,   # A-League
    "COL1":  0.58,   # Colombian Primera
    "EC1":   0.52,   # Ecuadorian Serie A
    "URU1":  0.55,   # Uruguayan Primera
    
    # International competitions
    "FIWC":  1.00,   # FIFA World Cup
    "EURO":  0.95,   # European Championship
    "COPA":  0.95,   # Copa America
    "AFAC":  0.90,   # Africa Cup of Nations
    "AFCN":  0.85,   # Asian Cup
    "GC":    0.80,   # Gold Cup
    
    # International qualifiers
    "WCQL":  0.80,   # World Cup qualifiers
    "EUCON": 0.75,   # Euro qualifiers
    "AFQL":  0.65,   # AFCON qualifiers
    "ACQL":  0.60,   # Asian Cup qualifiers
    "CNLQ":  0.55,   # CONCACAF Nations League qualifiers
    
    # Nations League
    "UNL":   0.80,   # UEFA Nations League
    "CNL":   0.70,   # CONCACAF Nations League
    
    # Domestic cups (lower weight)
    "FAC":   0.55,   # FA Cup
    "CDR":   0.55,   # Copa del Rey
    "DFB":   0.55,   # DFB-Pokal
    "CIT":   0.50,   # League Cup
    
    # Friendlies
    "FR":    0.35,   # International friendlies
}

# Position base ratings (different expectations per position)
POSITION_METRICS = {
    "GK":  {"goals_weight": 0.0,  "assists_weight": 0.05, "clean_sheet_weight": 2.0, "base": 60},
    "DF":  {"goals_weight": 0.8,  "assists_weight": 0.6,  "clean_sheet_weight": 1.0, "base": 55},
    "MF":  {"goals_weight": 0.7,  "assists_weight": 0.9,  "clean_sheet_weight": 0.3, "base": 55},
    "FW":  {"goals_weight": 1.2,  "assists_weight": 0.7,  "clean_sheet_weight": 0.0, "base": 50},
}

# Recency decay: exponential decay over time
# Half-life of ~18 months (540 days)
DECAY_HALF_LIFE_DAYS = 540
DECAY_LAMBDA = math.log(2) / DECAY_HALF_LIFE_DAYS

# Minimum appearances to be considered
MIN_APPEARANCES = 15
MIN_MINUTES = 1500  # ~17 full matches


# ============================================================
# Data Loading
# ============================================================

def load_player_appearances(player_ids=None, start_date=None):
    """Load all appearances for players since start_date."""
    if start_date is None:
        start_date = START_DATE
    
    if player_ids:
        placeholders = ','.join(['%s'] * len(player_ids))
        sql = f"""
            SELECT a.player_id, a.player_name, a.competition_id,
                   a.goals, a.assists, a.minutes_played,
                   a.yellow_cards, a.red_cards,
                   g.date, g.home_club_goals, g.away_club_goals,
                   a.player_club_id
            FROM tm_appearances a
            JOIN tm_games g ON a.game_id = g.game_id
            WHERE a.player_id IN ({placeholders})
              AND g.date >= %s
            ORDER BY a.player_id, g.date
        """
        return query(sql, list(player_ids) + [start_date], db='football_pred')
    else:
        sql = """
            SELECT a.player_id, a.player_name, a.competition_id,
                   a.goals, a.assists, a.minutes_played,
                   a.yellow_cards, a.red_cards,
                   g.date, g.home_club_goals, g.away_club_goals,
                   a.player_club_id
            FROM tm_appearances a
            JOIN tm_games g ON a.game_id = g.game_id
            WHERE g.date >= %s
            ORDER BY a.player_id, g.date
        """
        return query(sql, [start_date], db='football_pred')


def load_player_metadata(player_ids):
    """Load player metadata from tm_players."""
    if not player_ids:
        return {}
    
    placeholders = ','.join(['%s'] * len(player_ids))
    rows = query(
        f"SELECT player_id, name, position, sub_position, "
        f"current_club_id, current_club_name, market_value_in_eur, "
        f"date_of_birth, country_of_citizenship "
        f"FROM tm_players WHERE player_id IN ({placeholders})",
        list(player_ids), db='football_pred'
    )
    return {r['player_id']: r for r in rows}


# ============================================================
# Elo Calculation
# ============================================================

def get_position_category(position, sub_position=None):
    """Map position to category: GK, DF, MF, FW."""
    pos = (sub_position or position or '').lower()
    if 'goal' in pos or 'keeper' in pos:
        return 'GK'
    if 'back' in pos or 'defend' in pos or 'sweeper' in pos or 'wing-back' in pos:
        return 'DF'
    if 'midfield' in pos:
        return 'MF'
    if 'forward' in pos or 'winger' in pos or 'striker' in pos or 'attack' in pos:
        return 'FW'
    return 'MF'


def calc_recency_weight(match_date, ref_date=None):
    """Calculate recency weight with exponential decay."""
    if ref_date is None:
        ref_date = date.today()
    
    if isinstance(match_date, str):
        match_date = datetime.strptime(match_date, '%Y-%m-%d').date()
    
    days_ago = (ref_date - match_date).days
    return math.exp(-DECAY_LAMBDA * days_ago)


def calc_match_elo(goals, assists, minutes, yellow_cards, red_cards,
                   comp_weight, pos_metrics, home_goals=None, away_goals=None,
                   is_home=True, recency_weight=1.0):
    """
    Calculate Elo contribution from a single match.
    
    Returns a score that gets accumulated and normalized.
    """
    if minutes <= 0:
        return 0.0
    
    minutes_factor = min(minutes / 90.0, 1.0)  # Cap at 1.0 for 90+ minutes
    
    # Per-90 stats
    per_90 = 90.0 / max(minutes, 1)
    goals_90 = goals * per_90
    assists_90 = assists * per_90
    
    # Base performance score
    perf_score = (
        goals_90 * pos_metrics['goals_weight'] * 8.0 +
        assists_90 * pos_metrics['assists_weight'] * 5.0
    )
    
    # Clean sheet bonus for defenders/goalkeepers
    if pos_metrics['clean_sheet_weight'] > 0:
        if home_goals is not None and away_goals is not None:
            if (is_home and away_goals == 0) or (not is_home and home_goals == 0):
                perf_score += pos_metrics['clean_sheet_weight'] * 3.0
    
    # Card penalty
    card_penalty = yellow_cards * 0.5 + red_cards * 2.0
    perf_score -= card_penalty
    
    # Apply competition quality and recency
    weighted_score = perf_score * comp_weight * recency_weight * minutes_factor
    
    return weighted_score


def calculate_player_elo(player_id, appearances, player_meta=None):
    """
    Calculate comprehensive Elo rating for a single player.
    
    Returns dict with:
    - elo: Final Elo rating (0-99)
    - league_elo: Elo from league matches
    - intl_elo: Elo from international matches
    - breakdown: Detailed statistics
    """
    if not appearances:
        return None
    
    # Get position category
    if player_meta:
        pos_cat = get_position_category(
            player_meta.get('position'),
            player_meta.get('sub_position')
        )
    else:
        pos_cat = 'MF'  # Default
    
    pos_metrics = POSITION_METRICS.get(pos_cat, POSITION_METRICS['MF'])
    
    # Accumulate weighted scores
    total_weighted_score = 0.0
    total_weight = 0.0
    league_score = 0.0
    league_weight = 0.0
    intl_score = 0.0
    intl_weight = 0.0
    
    # Stats
    total_goals = 0
    total_assists = 0
    total_minutes = 0
    total_apps = 0
    total_yellow = 0
    total_red = 0
    
    league_apps = 0
    intl_apps = 0
    
    today = date.today()
    
    for app in appearances:
        comp_id = app.get('competition_id', '')
        comp_weight = COMPETITION_WEIGHT.get(comp_id, 0.5)
        
        # Recency weight
        match_date = app.get('date')
        if match_date:
            recency = calc_recency_weight(match_date, today)
        else:
            recency = 0.5
        
        goals = int(app.get('goals') or 0)
        assists = int(app.get('assists') or 0)
        minutes = int(app.get('minutes_played') or 0)
        yellow = int(app.get('yellow_cards') or 0)
        red = int(app.get('red_cards') or 0)
        
        # Determine if clean sheet
        home_goals = app.get('home_club_goals')
        away_goals = app.get('away_club_goals')
        
        # Calculate match contribution
        match_score = calc_match_elo(
            goals, assists, minutes, yellow, red,
            comp_weight, pos_metrics,
            home_goals, away_goals, True,  # Assume home for simplicity
            recency
        )
        
        total_weighted_score += match_score
        total_weight += comp_weight * recency * min(minutes / 90.0, 1.0)
        
        # Track stats
        total_goals += goals
        total_assists += assists
        total_minutes += minutes
        total_apps += 1
        total_yellow += yellow
        total_red += red
        
        # Separate league vs international
        is_intl = comp_id in ('FIWC', 'EURO', 'COPA', 'AFAC', 'AFCN', 'GC',
                              'WCQL', 'EUCON', 'AFQL', 'ACQL', 'CNLQ',
                              'UNL', 'CNL', 'FR')
        
        if is_intl:
            intl_score += match_score
            intl_weight += comp_weight * recency * min(minutes / 90.0, 1.0)
            intl_apps += 1
        else:
            league_score += match_score
            league_weight += comp_weight * recency * min(minutes / 90.0, 1.0)
            league_apps += 1
    
    # Normalize scores
    if total_weight > 0:
        avg_score = total_weighted_score / total_weight
    else:
        avg_score = 0
    
    if league_weight > 0:
        league_avg = league_score / league_weight
    else:
        league_avg = 0
    
    if intl_weight > 0:
        intl_avg = intl_score / intl_weight
    else:
        intl_avg = 0
    
    # Base Elo from position
    base_elo = pos_metrics['base']
    
    # Performance adjustment (scaled to reasonable range)
    # Typical good performance: +10 to +30
    perf_adjustment = avg_score * 2.0
    
    # Consistency bonus (more appearances = more reliable)
    consistency = min(total_apps / 40.0, 1.0) * 5.0
    
    # Volume bonus (significant minutes played)
    volume = min(total_minutes / 4000.0, 1.0) * 5.0
    
    # Sample reliability: penalize players with few minutes
    # Full reliability at 3000+ minutes, steep drop below 1500
    sample_reliability = min(total_minutes / 3000.0, 1.0) ** 0.5
    
    # Final Elo (0-99 scale)
    raw_elo = base_elo + (perf_adjustment + consistency + volume) * sample_reliability
    elo = round(max(0, min(99, raw_elo)), 1)
    
    # League-only and international-only Elo
    league_elo = round(max(0, min(99, base_elo + league_avg * 2.0 + consistency + volume)), 1)
    intl_elo = round(max(0, min(99, base_elo + intl_avg * 2.0 + consistency + volume)), 1) if intl_apps > 0 else None
    
    # Per-90 stats
    per_90_factor = 90.0 / max(total_minutes, 1)
    goals_per_90 = round(total_goals * per_90_factor, 3)
    assists_per_90 = round(total_assists * per_90_factor, 3)
    
    return {
        'player_id': player_id,
        'elo': elo,
        'league_elo': league_elo,
        'intl_elo': intl_elo,
        'position': pos_cat,
        'total_apps': total_apps,
        'total_minutes': total_minutes,
        'total_goals': total_goals,
        'total_assists': total_assists,
        'goals_per_90': goals_per_90,
        'assists_per_90': assists_per_90,
        'yellow_cards': total_yellow,
        'red_cards': total_red,
        'league_apps': league_apps,
        'intl_apps': intl_apps,
        'avg_score': round(avg_score, 3),
        'league_avg': round(league_avg, 3),
        'intl_avg': round(intl_avg, 3) if intl_apps > 0 else None,
    }


# ============================================================
# Batch Processing
# ============================================================

def calculate_elo_for_team(country_name, top_n=35):
    """
    Calculate Elo ratings for all players in a national team.
    
    This is the main entry point for the WC prediction engine.
    """
    from engine.wc_data import get_national_squad
    
    # Get squad from wc_data
    squad = get_national_squad(country_name, top_n=top_n)
    if not squad:
        return []
    
    player_ids = [p['player_id'] for p in squad]
    
    # Load all appearances for these players
    appearances = load_player_appearances(player_ids)
    
    # Load player metadata
    metadata = load_player_metadata(player_ids)
    
    # Group appearances by player
    player_appearances = defaultdict(list)
    for app in appearances:
        player_appearances[app['player_id']].append(app)
    
    # Calculate Elo for each player
    results = []
    for player_id in player_ids:
        apps = player_appearances.get(player_id, [])
        meta = metadata.get(player_id)
        
        if len(apps) >= MIN_APPEARANCES:
            elo_data = calculate_player_elo(player_id, apps, meta)
            if elo_data:
                # Add player info
                if meta:
                    elo_data['name'] = meta.get('name', '')
                    elo_data['club'] = meta.get('current_club_name', '')
                    elo_data['market_value'] = meta.get('market_value_in_eur', 0)
                    elo_data['country'] = meta.get('country_of_citizenship', '')
                results.append(elo_data)
    
    # Sort by Elo
    results.sort(key=lambda x: x['elo'], reverse=True)
    
    return results


def calculate_elo_for_all_players(min_appearances=10):
    """
    Calculate Elo ratings for ALL players with enough appearances.
    Useful for building a global player Elo database.
    """
    print(f"Loading all appearances since {START_DATE}...")
    all_appearances = load_player_appearances()
    
    # Group by player
    player_appearances = defaultdict(list)
    for app in all_appearances:
        player_appearances[app['player_id']].append(app)
    
    print(f"Found {len(player_appearances)} players with appearances")
    
    # Filter to players with enough appearances
    qualified = {pid: apps for pid, apps in player_appearances.items()
                 if len(apps) >= min_appearances}
    print(f"Qualified players ({min_appearances}+ apps): {len(qualified)}")
    
    # Load metadata in batches
    player_ids = list(qualified.keys())
    metadata = {}
    batch_size = 1000
    for i in range(0, len(player_ids), batch_size):
        batch = player_ids[i:i+batch_size]
        meta = load_player_metadata(batch)
        metadata.update(meta)
    
    # Calculate Elo
    results = []
    for i, (pid, apps) in enumerate(qualified.items()):
        meta = metadata.get(pid)
        elo_data = calculate_player_elo(pid, apps, meta)
        if elo_data:
            if meta:
                elo_data['name'] = meta.get('name', '')
                elo_data['club'] = meta.get('current_club_name', '')
                elo_data['market_value'] = meta.get('market_value_in_eur', 0)
                elo_data['country'] = meta.get('country_of_citizenship', '')
            results.append(elo_data)
        
        if (i + 1) % 5000 == 0:
            print(f"  Processed {i+1}/{len(qualified)}")
    
    results.sort(key=lambda x: x['elo'], reverse=True)
    return results


# ============================================================
# Utility Functions
# ============================================================

def get_team_avg_elo(country_name, top_n=11):
    """Get average Elo of top N players for a national team."""
    players = calculate_elo_for_team(country_name, top_n=top_n * 2)
    if not players:
        return 50.0  # Default
    
    top_players = players[:top_n]
    if not top_players:
        return 50.0
    
    return round(sum(p['elo'] for p in top_players) / len(top_players), 1)


def get_team_elo_breakdown(country_name):
    """Get detailed Elo breakdown for a national team."""
    players = calculate_elo_for_team(country_name)
    if not players:
        return None
    
    # Position groups
    gk = [p for p in players if p['position'] == 'GK']
    df = [p for p in players if p['position'] == 'DF']
    mf = [p for p in players if p['position'] == 'MF']
    fw = [p for p in players if p['position'] == 'FW']
    
    def avg_elo(lst, n=3):
        top = lst[:n]
        return round(sum(p['elo'] for p in top) / max(len(top), 1), 1) if top else 50.0
    
    return {
        'country': country_name,
        'total_players': len(players),
        'avg_elo': round(sum(p['elo'] for p in players) / len(players), 1),
        'top_11_avg': avg_elo(players, 11),
        'gk_elo': avg_elo(gk, 2),
        'df_elo': avg_elo(df, 4),
        'mf_elo': avg_elo(mf, 3),
        'fw_elo': avg_elo(fw, 3),
        'best_player': players[0] if players else None,
        'top_5': players[:5],
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        country = sys.argv[1]
        print(f"\n=== Elo Analysis: {country} ===\n")
        
        breakdown = get_team_elo_breakdown(country)
        if breakdown:
            print(f"Total players: {breakdown['total_players']}")
            print(f"Average Elo: {breakdown['avg_elo']}")
            print(f"Top 11 Avg: {breakdown['top_11_avg']}")
            print(f"  GK: {breakdown['gk_elo']}")
            print(f"  DF: {breakdown['df_elo']}")
            print(f"  MF: {breakdown['mf_elo']}")
            print(f"  FW: {breakdown['fw_elo']}")
            print()
            print("Top 5 players:")
            for p in breakdown['top_5']:
                intl = f"Intl Elo: {p['intl_elo']}" if p['intl_elo'] else "No intl data"
                print(f"  {p['name']:25s} Elo={p['elo']:5.1f} "
                      f"League={p['league_elo']:5.1f} {intl}")
                print(f"    {p['total_apps']} apps, {p['total_goals']}G {p['total_assists']}A "
                      f"({p['goals_per_90']:.2f}G/90 {p['assists_per_90']:.2f}A/90)")
        else:
            print("No data found")
    else:
        print("Usage: python wc_player_elo.py <country_name>")
        print("Example: python wc_player_elo.py Brazil")

