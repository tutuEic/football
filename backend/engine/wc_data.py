# -*- coding: utf-8 -*-
"""
World Cup Data Layer 閳?Squad Analysis & Player Elo
===================================================
Queries tm_players by nationality, computes per-team strength metrics.

Each sub-factor is quantified with clear range and meaning:
  - player_strength:  0-99   (composite rating per player)
  - starting_xi:      0-99   (top-11 average strength)
  - attack_quality:   0-99   (top-5 attacker average)
  - defense_quality:  0-99   (top-5 defender average)
  - squad_depth:      0-99   (top-23 average minus penalty)
  - age_score:        0.0-1.0 (peak-age proportion)
  - league_quality:   0-100  (weighted league strength)
  - cohesion:         0.0-1.0 (league/club concentration)
  - set_piece:        0.0-1.0 (height + GK + scorers)
  - elo_bonus:        -60 ~ +120 (combined Elo adjustment)
"""
import math
import sys
import os
from datetime import date
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query

# ============================================================
# Country name mapping: FIFA API name -> tm_players.country_of_citizenship
# ============================================================
COUNTRY_MAP = {
    "Korea Republic":        "Korea, South",
    "IR Iran":               "Iran",
    "Turkiye":               "Türkiye",
    "Congo DR":              "DR Congo",
    "USA":                   "United States",
    "Cabo Verde":            "Cape Verde",
    "Bosnia and Herzegovina":"Bosnia-Herzegovina",
    "Czechia":               "Czech Republic",
}

# Domestic league code per country (for cohesion calculation)
DOMESTIC_LEAGUE = {
    "France":           "FR1",  "Spain":            "ES1",
    "Germany":          "L1",   "Italy":            "IT1",
    "England":          "GB1",  "Netherlands":      "NL1",
    "Portugal":         "PO1",  "Turkey":           "TR1",
    "Belgium":          "BE1",  "Brazil":           "BRA1",
    "Argentina":        "ARG1", "Mexico":           "MEX1",
    "Japan":            "JAP1", "South Korea":      "KR1",
    "Saudi Arabia":     "SA1",  "Colombia":         "COL1",
    "Scotland":         "SC1",  "Denmark":          "DK1",
    "Norway":           "NO1",  "Austria":          "A1",
    "Switzerland":      "CH1",  "Serbia":           "SER1",
    "Czech Republic":   "CZ1",  "Greece":           "GR1",
    "Russia":           "RU1",  "Romania":          "RO1",
    "Sweden":           "SE1",  "Croatia":          "HR1",
    "Egypt":            "EG1",  "Morocco":          "MAR1",
    "Nigeria":          "NGA1", "Senegal":          "SEN1",
    "Tunisia":          "TUN1", "Algeria":          "ALG1",
    "Ghana":            "GHA1", "Cameroon":         "CMR1",
    "Australia":        "AUS1", "Iran":             "IRN1",
    "Iraq":             "IRQ1", "Ecuador":          "EC1",
    "Uruguay":          "URU1", "Paraguay":         "PAR1",
    "Peru":             "PER1", "Canada":           "MLS1",
    "Panama":           "MLS1", "Jamaica":          "MLS1",
    "Haiti":            "MLS1", "Costa Rica":       "MLS1",
    "DR Congo":         "CD1",  "Ivory Coast":      "CI1",
    "South Africa":     "ZA1",  "New Zealand":      "AUS1",
    "Jordan":           "JOR1", "Uzbekistan":       "UZ1",
    "Wales":            "GB1",  "Qatar":            "QAT1",
    "Cape Verde":       "PO1",
    "Cote d'Ivoire":    "CI1",
}

# League quality: 0-100 scale
LEAGUE_QUALITY = {
    "GB1": 95, "ES1": 93, "L1": 90, "IT1": 90, "FR1": 88,
    "CL": 100, "EL": 85, "NL1": 78, "PO1": 76, "BE1": 72, "TR1": 72,
    "SC1": 68, "DK1": 68, "NO1": 65, "A1": 67, "SER1": 62, "CZ1": 60,
    "GR1": 58, "SE1": 62, "RO1": 55, "RU1": 58, "CH1": 65,
    "ARG1": 70, "BRA1": 68, "COL1": 62, "URU1": 58, "EC1": 52,
    "PAR1": 50, "PER1": 48,
    "MLS1": 62, "MEX1": 65,
    "JAP1": 62, "KR1": 60, "SA1": 58, "AUS1": 55, "QAT1": 50,
    "IRN1": 48, "IRQ1": 45,
    "MAR1": 50, "EG1": 48, "SEN1": 48, "NGA1": 46, "TUN1": 45,
    "ALG1": 45, "GHA1": 44, "CI1": 45, "CMR1": 42, "CD1": 40, "ZA1": 42,
    "HR1": 55, "BA1": 48, "UZ1": 40, "JOR1": 38,
}

# Position base ratings (from player_ratings.py)
POSITION_BASE = {
    "Goalkeeper":        {"attack": 15, "defense": 75, "pace": 55, "passing": 40, "physical": 70},
    "Centre-Back":       {"attack": 25, "defense": 82, "pace": 60, "passing": 55, "physical": 80},
    "Left-Back":         {"attack": 45, "defense": 72, "pace": 78, "passing": 65, "physical": 68},
    "Right-Back":        {"attack": 45, "defense": 72, "pace": 78, "passing": 65, "physical": 68},
    "Defensive Midfield":{"attack": 40, "defense": 75, "pace": 62, "passing": 72, "physical": 72},
    "Central Midfield":  {"attack": 60, "defense": 60, "pace": 65, "passing": 78, "physical": 68},
    "Attacking Midfield":{"attack": 75, "defense": 35, "pace": 72, "passing": 82, "physical": 62},
    "Left Winger":       {"attack": 78, "defense": 25, "pace": 85, "passing": 75, "physical": 58},
    "Right Winger":      {"attack": 78, "defense": 25, "pace": 85, "passing": 75, "physical": 58},
    "Centre-Forward":    {"attack": 85, "defense": 20, "pace": 78, "passing": 65, "physical": 72},
    "Second Striker":    {"attack": 80, "defense": 25, "pace": 75, "passing": 72, "physical": 65},
    "Attack":            {"attack": 78, "defense": 25, "pace": 78, "passing": 68, "physical": 65},
    "Midfield":          {"attack": 55, "defense": 55, "pace": 66, "passing": 74, "physical": 66},
    "Defender":          {"attack": 35, "defense": 78, "pace": 68, "passing": 58, "physical": 75},
    "Sweeper":           {"attack": 25, "defense": 80, "pace": 55, "passing": 60, "physical": 75},
    "Wing-Back":         {"attack": 55, "defense": 68, "pace": 80, "passing": 68, "physical": 65},
}


def _country_name(fifa_name):
    """Map FIFA API country name to tm_players.country_of_citizenship."""
    return COUNTRY_MAP.get(fifa_name, fifa_name)


def _pos_category(pos):
    """Map position string to category: GK, DF, MF, FW."""
    if not pos:
        return "MF"
    p = pos.lower()
    if "goal" in p or "keeper" in p:
        return "GK"
    if "back" in p or "defend" in p or "sweeper" in p or "wing-back" in p:
        return "DF"
    if "midfield" in p:
        return "MF"
    if "forward" in p or "winger" in p or "striker" in p or "attack" in p:
        return "FW"
    return "MF"


# ============================================================
# 1. Query national squad 閳?ACTIVE players only (2024+ appearances)
# ============================================================
def get_national_squad(fifa_country_name, top_n=35):
    """
    Query tm_players for a national team.
    Two-step approach for performance:
      Step 1: Get players from tm_players (fast, filtered by country + market_value)
      Step 2: Batch-query tm_appearances stats for those players (single query)
    Filters: active players preferred (2024+ appearances), age < 42.
    Returns top N players by market_value.
    """
    country = _country_name(fifa_country_name)

    # Step 1: Get candidate players (fast query, no JOIN with appearances)
    rows = query("""
        SELECT p.player_id, p.name, p.position, p.sub_position,
               p.current_club_id, p.current_club_name,
               c.domestic_competition_id AS league,
               p.market_value_in_eur AS market_value,
               p.height_in_cm AS height_cm,
               p.date_of_birth
        FROM tm_players p
        LEFT JOIN tm_clubs c ON p.current_club_id = c.club_id
        WHERE p.country_of_citizenship = %s
          AND p.market_value_in_eur > 0
          AND p.date_of_birth >= '1988-06-01'
        ORDER BY p.market_value_in_eur DESC
        LIMIT %s
    """, [country, top_n], db="football_pred")

    if not rows:
        return []

    # Step 2: Batch-query appearance stats for these players
    player_ids = [r["player_id"] for r in rows]
    placeholders = ",".join(["%s"] * len(player_ids))
    stats_rows = query(f"""
        SELECT a.player_id,
               SUM(a.goals) AS total_goals,
               SUM(a.assists) AS total_assists,
               SUM(a.minutes_played) AS total_mins,
               COUNT(*) AS total_apps
        FROM tm_appearances a
        JOIN tm_games g ON a.game_id = g.game_id
        WHERE a.player_id IN ({placeholders})
          AND g.date >= '2024-01-01'
        GROUP BY a.player_id
    """, player_ids, db="football_pred")

    # Build stats lookup
    stats_map = {}
    for s in stats_rows:
        stats_map[s["player_id"]] = {
            "total_goals":   int(s["total_goals"] or 0),
            "total_assists": int(s["total_assists"] or 0),
            "total_mins":    int(s["total_mins"] or 0),
            "total_apps":    int(s["total_apps"] or 0),
        }

    # Step 3: Merge, filter inactive, and build player list
    # Use a helper to allow two-pass filtering for small nations
    today = date.today()

    def _build_filtered(min_mv_threshold):
        """Build player list, keeping active players and those above mv threshold."""
        result = []
        for r in rows:
            pid = r["player_id"]
            st = stats_map.get(pid, {})
            apps = st.get("total_apps", 0)
            mv = int(r.get("market_value") or 0)
            # Keep: has 2024+ appearances, OR market value >= threshold
            if apps == 0 and mv < min_mv_threshold:
                continue
            result.append((r, pid, st, mv))
        return result

    # Pass 1: strict (active OR >= 10M)
    candidates = _build_filtered(10_000_000)
    # Pass 2: relax if < 11 players
    if len(candidates) < 11:
        candidates = _build_filtered(1_000_000)
    # Pass 3: include anyone with market value > 0
    if len(candidates) < 11:
        candidates = _build_filtered(0)

    players = []
    for r, pid, st, mv in candidates:
        dob = r.get("date_of_birth")
        if dob:
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        else:
            age = 25

        total_mins    = st.get("total_mins", 0)
        total_apps    = st.get("total_apps", 0)
        total_goals   = st.get("total_goals", 0)
        total_assists = st.get("total_assists", 0)

        if total_mins > 90:
            goals_per_90   = round(total_goals / (total_mins / 90), 3)
            assists_per_90 = round(total_assists / (total_mins / 90), 3)
        else:
            goals_per_90   = 0.0
            assists_per_90 = 0.0

        players.append({
            "player_id":       pid,
            "name":            r["name"],
            "position":        r.get("sub_position") or r.get("position") or "Midfield",
            "pos_category":    _pos_category(r.get("sub_position") or r.get("position")),
            "club_id":         r.get("current_club_id"),
            "club_name":       r.get("current_club_name", ""),
            "league":          r.get("league") or "",
            "market_value":    int(r.get("market_value") or 0),
            "height_cm":       int(r.get("height_cm") or 178),
            "age":             age,
            "total_apps":      total_apps,
            "total_mins":      total_mins,
            "total_goals":     total_goals,
            "total_assists":   total_assists,
            "goals_per_90":    goals_per_90,
            "assists_per_90":  assists_per_90,
        })

    return players


# ============================================================
# 2. Player Strength Score (0-99) 閳?uses actual performance stats
# ============================================================
def calc_player_strength(player):
    """
    Composite strength for a single player.
    Uses position base + market value + per-90 performance stats.
    Range: 0-99

    Formula:
      base = position_default_attack/defense average
      mv_bonus = log10(market_value) * 2 - 10  (capped at +15)
      perf_bonus = goals_per_90 * 8 + assists_per_90 * 6  (capped at +15)
      strength = base + mv_bonus + perf_bonus
    """
    pos = player.get("position", "Midfield")
    base = POSITION_BASE.get(pos, POSITION_BASE["Midfield"])

    # Position-aware base: weight attributes by role (target ~45-58 range)
    cat = _pos_category(player.get("position") or "")
    if cat == "GK":
        pos_overall = base["defense"] * 0.55 + base["physical"] * 0.10
    elif cat == "DF":
        pos_overall = base["defense"] * 0.45 + base["physical"] * 0.12 + base["pace"] * 0.08
    elif cat == "FW":
        pos_overall = base["attack"] * 0.48 + base["pace"] * 0.12 + base["passing"] * 0.08
    else:  # MF
        pos_overall = base["attack"] * 0.25 + base["defense"] * 0.15 + base["passing"] * 0.25

    # Market value bonus: log10 scale (capped at +20)
    mv = player.get("market_value", 0)
    if mv > 0:
        mv_bonus = max(min(math.log10(mv) * 2.5 - 12, 20), 0)
    else:
        mv_bonus = 0

    # Performance bonus from actual stats (goals + assists per 90)
    goals_90 = player.get("goals_per_90", 0)
    assists_90 = player.get("assists_per_90", 0)
    perf_bonus = min(goals_90 * 8 + assists_90 * 6, 15)

    # Minutes bonus: sustained high minutes = consistent performer
    mins = player.get("total_mins", 0)
    if mins >= 3000:
        mins_bonus = 5
    elif mins >= 2000:
        mins_bonus = 3
    elif mins >= 1000:
        mins_bonus = 1
    else:
        mins_bonus = 0

    # Appearance weight: more appearances = more reliable rating
    apps = player.get("total_apps", 0)
    if apps >= 40:
        app_weight = 1.0
    elif apps >= 25:
        app_weight = 0.95
    elif apps >= 15:
        app_weight = 0.90
    elif apps >= 5:
        app_weight = 0.80
    elif apps >= 1:
        app_weight = 0.70
    else:
        app_weight = 0.50

    # Composite
    raw = pos_overall + mv_bonus + perf_bonus + mins_bonus
    strength = raw * app_weight
    return round(min(max(strength, 0), 99), 1)


# ============================================================
# 3. Squad Aggregation: Starting XI, Attack, Defense, Depth
# ============================================================
def calc_squad_ratings(squad):
    """
    Compute team-level ratings from player list.
    Returns dict with starting_xi, attack_quality, defense_quality, squad_depth.
    Range: 0-99 for each.
    """
    if not squad:
        return {"starting_xi": 50, "attack_quality": 50,
                "defense_quality": 50, "squad_depth": 50}

    for p in squad:
        p["strength"] = calc_player_strength(p)

    # Formation-based Starting XI: 1 GK + 4 DF + 3 MF + 3 FW
    sorted_players = sorted(squad, key=lambda p: p["strength"], reverse=True)
    by_cat = {"GK": [], "DF": [], "MF": [], "FW": []}
    for p in squad:
        cat = p.get("pos_category", "MF")
        by_cat.setdefault(cat, []).append(p)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda p: p["strength"], reverse=True)

    xi_slots = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
    top_11 = []
    for cat, count in xi_slots.items():
        top_11.extend(by_cat.get(cat, [])[:count])
    # Fallback: if a category is short, fill from best remaining
    if len(top_11) < 11:
        used_ids = {p["player_id"] for p in top_11}
        remaining = [p for p in squad if p["player_id"] not in used_ids]
        remaining.sort(key=lambda p: p["strength"], reverse=True)
        top_11.extend(remaining[:11 - len(top_11)])

    starting_xi = round(sum(p["strength"] for p in top_11) / max(len(top_11), 1), 1)

    # Attack quality: top 5 attackers/midfielders
    attackers = [p for p in sorted_players if p["pos_category"] in ("FW", "MF")]
    top_5_att = attackers[:5]
    attack_quality = round(sum(p["strength"] for p in top_5_att) / max(len(top_5_att), 1), 1)

    # Defense quality: top 5 defenders + GK
    defenders = [p for p in sorted_players if p["pos_category"] in ("DF", "GK")]
    top_5_def = defenders[:5]
    defense_quality = round(sum(p["strength"] for p in top_5_def) / max(len(top_5_def), 1), 1)

    # Squad depth: top 23 average minus std penalty
    top_23 = sorted_players[:23]
    if len(top_23) >= 2:
        mean_23 = sum(p["strength"] for p in top_23) / len(top_23)
        variance = sum((p["strength"] - mean_23) ** 2 for p in top_23) / len(top_23)
        std_23 = math.sqrt(variance)
        squad_depth = round(mean_23 - std_23 * 0.3, 1)
    else:
        squad_depth = 50.0

    return {
        "starting_xi":     starting_xi,
        "attack_quality":  attack_quality,
        "defense_quality": defense_quality,
        "squad_depth":     max(squad_depth, 0),
    }


def calc_starting_xi_elo(starting_xi_score):
    """Map starting XI score (0-99) to Elo bonus. Range: -40 to +80."""
    if starting_xi_score >= 85:
        return 80
    elif starting_xi_score >= 78:
        return 50
    elif starting_xi_score >= 70:
        return 25
    elif starting_xi_score >= 60:
        return 0
    elif starting_xi_score >= 50:
        return -20
    else:
        return -40


def calc_star_bonus(squad):
    """If the top player has strength > 80, add +5 Elo."""
    if not squad:
        return 0
    strengths = [p.get("strength", 0) for p in squad]
    if max(strengths) > 80:
        return 5
    return 0


# ============================================================
# 4. Age Profile
# ============================================================
def calc_age_profile(squad):
    """Score based on age distribution. Peak: 26-29. Returns (age_score, avg_age)."""
    if not squad:
        return 0.6, 25.0

    age_factor = 0.0
    ages = []
    for p in squad:
        age = p.get("age", 25)
        ages.append(age)
        if 26 <= age <= 29:
            age_factor += 1.0
        elif 24 <= age <= 25:
            age_factor += 0.7
        elif 30 <= age <= 32:
            age_factor += 0.6
        elif age < 24:
            age_factor += 0.3
        else:
            age_factor += 0.2

    score = age_factor / max(len(squad), 1)
    avg_age = sum(ages) / max(len(ages), 1)
    return round(score, 3), round(avg_age, 1)


def calc_age_elo(age_score):
    """Map age_score (0-1) to Elo bonus. Range: -30 to +30."""
    return round((age_score - 0.6) * 75, 1)


# ============================================================
# 5. League Quality
# ============================================================
def calc_league_quality(squad):
    """Average league quality of top-15 players. Range: 0-100."""
    leagues = []
    for p in squad[:15]:
        lg = p.get("league", "")
        leagues.append(LEAGUE_QUALITY.get(lg, 45))
    if not leagues:
        return 50.0
    return round(sum(leagues) / len(leagues), 1)


def calc_league_elo(league_quality):
    """Map league_quality (0-100) to Elo bonus. Range: -20 to +30."""
    return round((league_quality - 70) * 1.0, 1)


# ============================================================
# 6. Squad Cohesion
# ============================================================
def calc_cohesion(squad, country=None):
    """
    Measure squad cohesion: league concentration (0.4) + club concentration (0.3)
    + domestic ratio (0.3). Range: 0.0-1.0.
    """
    if not squad:
        return 0.5

    n = len(squad)

    leagues = [p.get("league", "") for p in squad if p.get("league")]
    if leagues:
        league_counts = Counter(leagues)
        league_conc = league_counts.most_common(1)[0][1] / n
    else:
        league_conc = 0.3

    clubs = [p.get("club_id") for p in squad if p.get("club_id")]
    if clubs:
        club_counts = Counter(clubs)
        club_conc = club_counts.most_common(1)[0][1] / n
    else:
        club_conc = 0.1

    domestic_ratio = 0.3
    if country:
        domestic_league = DOMESTIC_LEAGUE.get(_country_name(country), "")
        if domestic_league:
            domestic_count = sum(1 for p in squad if p.get("league") == domestic_league)
            domestic_ratio = domestic_count / n

    cohesion = league_conc * 0.4 + club_conc * 0.3 + domestic_ratio * 0.3
    return round(min(max(cohesion, 0), 1), 3)


def calc_cohesion_elo(cohesion):
    """Map cohesion (0-1) to Elo bonus. Range: -30 to +30."""
    return round((cohesion - 0.5) * 60, 1)


# ============================================================
# 7. Set Piece Strength
# ============================================================
def calc_set_piece_strength(squad):
    """
    Set piece ability: height (0.35) + attacker quality (0.35) + GK quality (0.30).
    Range: 0.0-1.0.
    """
    if not squad:
        return 0.5

    outfield = [p for p in squad if p.get("pos_category") != "GK"]
    if outfield:
        avg_height = sum(p.get("height_cm", 178) for p in outfield) / len(outfield)
        height_score = max(min((avg_height - 178) / 10, 1.5), -0.5)
    else:
        height_score = 0.0

    attackers = [p for p in squad if p.get("pos_category") in ("FW", "MF")]
    attackers.sort(key=lambda p: p.get("strength", 0), reverse=True)
    top_attackers = attackers[:5]
    if top_attackers:
        att_avg = sum(p.get("strength", 50) for p in top_attackers) / len(top_attackers)
        scorer_score = att_avg / 100
    else:
        scorer_score = 0.5

    gks = [p for p in squad if p.get("pos_category") == "GK"]
    if gks:
        best_gk = max(gks, key=lambda p: p.get("strength", 0))
        gk_score = best_gk.get("strength", 60) / 100
    else:
        gk_score = 0.6

    set_piece = height_score * 0.35 + scorer_score * 0.35 + gk_score * 0.30
    return round(max(min(set_piece, 1.0), 0.0), 3)


def calc_setpiece_elo(set_piece_score):
    """Map set_piece (0-1) to Elo bonus. Range: -20 to +20."""
    return round((set_piece_score - 0.5) * 40, 1)


# ============================================================
# 8. Main Entry: Full Squad Analysis
# ============================================================
_squad_analysis_cache = {}


def analyze_squad(fifa_country_name):
    """Full squad analysis for a national team."""
    if fifa_country_name in _squad_analysis_cache:
        return _squad_analysis_cache[fifa_country_name]

    squad = get_national_squad(fifa_country_name, top_n=35)
    if not squad:
        return _empty_analysis(fifa_country_name)

    for p in squad:
        p["strength"] = calc_player_strength(p)

    ratings = calc_squad_ratings(squad)
    age_score, avg_age = calc_age_profile(squad)
    league_q = calc_league_quality(squad)
    cohesion = calc_cohesion(squad, fifa_country_name)
    setpiece = calc_set_piece_strength(squad)

    xi_elo       = calc_starting_xi_elo(ratings["starting_xi"])
    age_elo      = calc_age_elo(age_score)
    league_elo   = calc_league_elo(league_q)
    cohesion_elo = calc_cohesion_elo(cohesion)
    sp_elo       = calc_setpiece_elo(setpiece)
    star_elo     = calc_star_bonus(squad)

    total_elo = xi_elo + age_elo + league_elo + cohesion_elo + sp_elo + star_elo

    top_players = sorted(squad, key=lambda p: p["strength"], reverse=True)[:5]
    top_display = [f"{p['name']} ({p['strength']:.0f})" for p in top_players]

    result = {
        "country":            fifa_country_name,
        "tm_country":         _country_name(fifa_country_name),
        "squad_size":         len(squad),
        "starting_xi":        ratings["starting_xi"],
        "attack_quality":     ratings["attack_quality"],
        "defense_quality":    ratings["defense_quality"],
        "squad_depth":        ratings["squad_depth"],
        "avg_age":            avg_age,
        "age_score":          age_score,
        "league_quality":     league_q,
        "cohesion":           cohesion,
        "set_piece_strength": setpiece,
        "elo_bonus":          round(total_elo, 1),
        "elo_breakdown": {
            "starting_xi": xi_elo, "age": age_elo, "league": league_elo,
            "cohesion": cohesion_elo, "set_piece": sp_elo, "star": star_elo,
        },
        "top_players":        top_display,
        "squad":              squad,
    }
    _squad_analysis_cache[fifa_country_name] = result
    return result

def _empty_analysis(country):
    """Return default analysis when no player data found."""
    return {
        "country": country, "tm_country": _country_name(country),
        "squad_size": 0, "starting_xi": 50.0, "attack_quality": 50.0,
        "defense_quality": 50.0, "squad_depth": 50.0, "avg_age": 25.0,
        "age_score": 0.5, "league_quality": 45.0, "cohesion": 0.4,
        "set_piece_strength": 0.5, "elo_bonus": -20.0,
        "elo_breakdown": {"starting_xi": -20, "age": 0, "league": 0,
                          "cohesion": 0, "set_piece": 0, "star": 0},
        "top_players": [], "squad": [],
    }


def analyze_all_wc_teams():
    """Run analyze_squad for all 48 WC teams from wc_groups table."""
    rows = query("SELECT DISTINCT team FROM wc_groups ORDER BY team", db="football_pred")
    results = {}
    for r in rows:
        team = r["team"]
        try:
            results[team] = analyze_squad(team)
        except Exception as e:
            print(f"[WC_DATA] Error analyzing {team}: {e}")
            results[team] = _empty_analysis(team)
    return results
