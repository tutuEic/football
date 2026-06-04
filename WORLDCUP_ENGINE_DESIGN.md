# World Cup Prediction Engine Design - Complete

## Problem Statement

The existing league engine relies on trained DC models, club-level Transfermarkt data,
and same-league history. None of these work for the World Cup.
We need a from-scratch international engine built on 6 layers + 9 supplementary factors.

---

## Core Architecture: 6-Layer Model

```
+------------------------------------------------------+
| Layer 6: Match Context                                |
|   Stage / Home advantage / Importance / Fatigue       |
+------------------------------------------------------+
| Layer 5: Tournament Factors                           |
|   WC history / Continental style / Historical curses  |
+------------------------------------------------------+
| Layer 4: Form & Momentum                              |
|   Qualifiers / Friendlies / Continental championships |
+------------------------------------------------------+
| Layer 3: Strength Decomposition                       |
|   Attack/Defense split + Player position quality      |
+------------------------------------------------------+
| Layer 2: Base Elo                                     |
|   FIFA ranking + Confederation calibration            |
+------------------------------------------------------+
| Layer 1: Player Elo                                   |
|   Squad quality + Age + League + Cohesion + Set pieces|
+------------------------------------------------------+
```

---

## Layer 1: Player Elo (with 5 sub-factors)

This is the foundation. It aggregates individual player data into
a team-level strength adjustment.

### 1a. Core Player Strength

Data: `tm_players` (47,669 players) with `country_of_citizenship`.

```
player_strength = overall_rating * 0.6 + market_value_score * 0.4
market_value_score = min(log10(max(market_value_eur, 1)) * 10, 99)
```

Squad aggregation:
- starting_xi = mean(top_11.strength) -> Elo bonus (-40 to +80)
- attack_quality = mean(top_5_attackers.strength)
- defense_quality = mean(top_5_defenders.strength)
- depth = mean(top_23.strength) - std(top_23.strength) * 0.3

Star player bonus: top player > 88 -> +5 Elo.

### 1b. Age Profile

WC peak performance age: 26-29. Analysis of `tm_players.date_of_birth`.

```
age_factor = 0.0
for player in squad:
    age = current_year - player.year_of_birth
    if 26 <= age <= 29:
        age_factor += 1.0    # Peak
    elif 24 <= age <= 25:
        age_factor += 0.7    # Rising
    elif 30 <= age <= 32:
        age_factor += 0.6    # Experienced but declining
    elif age < 24:
        age_factor += 0.3    # Too young
    else:
        age_factor += 0.2    # Too old

age_score = age_factor / len(squad)   # 0 to 1
age_elo = (age_score - 0.6) * 100     # -60 to +40 Elo
```

### 1c. League Quality

Players in stronger leagues are better prepared for WC intensity.

```python
LEAGUE_QUALITY = {
    'GB1': 95, 'ES1': 93, 'L1': 90, 'IT1': 90, 'FR1': 88,
    'NL1': 78, 'PO1': 76, 'TR1': 72,
    'MLS1': 65, 'JAP1': 62, 'KR1': 60, 'SA1': 58,
    'ARG1': 70, 'BRA1': 68, 'COL1': 62,
    'CL': 100, 'EL': 85, 'EURO': 90, 'COPA': 75,
}

# For each player, get their club's domestic_competition_id
league_score = mean(top_15_players.league_quality)
league_elo = (league_score - 70) * 1.0   # -20 to +30 Elo
```

### 1d. Squad Cohesion (球队磨合度)

National teams have limited training time. Teams with players from fewer
different clubs/leagues have better on-field understanding.

```python
def calc_cohesion(squad):
    # 1. League concentration: % of players from the same league
    leagues = [p.league for p in squad]
    most_common_count = max(leagues.count(l) for l in set(leagues))
    league_concentration = most_common_count / len(leagues)
    # Spain: 90%+ La Liga -> high cohesion
    # African teams: scattered across many leagues -> lower cohesion

    # 2. Club concentration: % from the same club
    clubs = [p.club_id for p in squad]
    most_common_club = max(clubs.count(c) for c in set(clubs))
    club_concentration = most_common_club / len(clubs)
    # e.g., Barcelona-heavy Spain, Bayern-heavy Germany

    # 3. National league presence: how many play in their OWN domestic league
    domestic_league = get_domestic_league(country)
    domestic_count = sum(1 for p in squad if p.league == domestic_league)
    domestic_ratio = domestic_count / len(squad)
    # Higher = more familiar with each other

    # Composite cohesion score (0-1)
    cohesion = (league_concentration * 0.4 +
                club_concentration * 0.3 +
                domestic_ratio * 0.3)
    return cohesion

cohesion_elo = (cohesion - 0.5) * 60   # -30 to +30 Elo
```

Expected impact:
- Spain (90%+ La Liga): +25 Elo
- England (95%+ Premier League): +25 Elo
- Morocco (scattered across Europe): -10 Elo
- Haiti (mostly domestic/MLS): +5 Elo (high domestic ratio)

### 1e. Set Piece Ability (定位球能力)

WC games are typically tighter and more tactical than league games.
Set pieces (corners, free kicks, penalties) account for ~30% of WC goals.

```python
def calc_set_piece_strength(squad):
    # 1. Height advantage: average height of outfield starters
    heights = [p.height_cm for p in squad if p.position != 'Goalkeeper']
    avg_height = mean(heights)
    # Taller teams have advantage in aerial duels (corners, FK)
    height_score = (avg_height - 180) / 10   # -2 to +2

    # 2. Goal-scoring from non-open-play (proxy from appearances)
    # Players with high goals relative to minutes may be set-piece takers
    set_piece_scorers = sum(1 for p in squad
        if p.goals_per_90 > 0.2 and p.position in ('Midfield', 'Attack'))
    scorer_density = set_piece_scorers / max(len(squad), 1)

    # 3. GK penalty-save ability (height + reflexes proxy)
    gks = [p for p in squad if p.position == 'Goalkeeper']
    gk_quality = mean([p.overall for p in gks]) if gks else 60

    # Composite (0-1)
    set_piece = (height_score * 0.35 +
                 scorer_density * 10 * 0.35 +
                 gk_quality / 100 * 0.3)
    set_piece = max(0, min(set_piece, 1))
    return set_piece

sp_elo = (set_piece - 0.5) * 40   # -20 to +20 Elo
```

### Layer 1 Total
```
player_elo_bonus = (starting_xi_elo + age_elo + league_elo +
                    cohesion_elo + sp_elo + star_bonus)
```

---

## Layer 2: Base Elo

From FIFA ranking (stored in `wc_groups.elo_rating`).

### Confederation Adjustment
| Confederation | Factor |
|---|---|
| UEFA | 1.00 |
| CONMEBOL | 0.98 |
| CAF | 0.92 |
| CONCACAF | 0.90 |
| AFC | 0.88 |
| OFC | 0.78 |

Cross-confederation: `bonus = (opp_factor - own_factor) * 20` (max ~4 Elo).

### Combined Elo
```
combined_elo = fifa_elo + player_elo_bonus + confederation_adj
```

---

## Layer 3: Strength Decomposition

### Default (Elo-only)
```
alpha = (combined_elo - 1500) / 800 * 0.6
beta  = -(combined_elo - 1500) / 800 * 0.4
```

### Player-Quality Adjusted
```
att_q = (attack_quality - 70) / 30
def_q = (defense_quality - 70) / 30

alpha = base_att * 0.6 + att_q * 0.3 * 0.4
beta  = base_def * 0.6 + def_q * 0.3 * (-0.2)
```

---

## Layer 4: Form & Momentum

Data sources with weights:
1. WC Qualifying -- weight 1.0 (from fixtures/tm_games)
2. Continental championship (EURO/COPA/AFAC/AFCN) -- weight 0.8
3. Recent friendlies -- weight 0.4

```
form = sum(result_i * weight_i * exp(-0.2 * i)) / sum(weight_i * exp(-0.2 * i))
result: +1.2 (win 2+), +1.0 (win), +0.3 (draw), -0.5 (loss), -0.8 (loss 2+)
```

Impact: `lam *= (1 + form * 0.15)`

---

## Layer 5: Tournament Factors

### 5a. WC Historical Performance
From `tm_games` (FIWC = 320 matches) + hardcoded best results.

| Best Result | Elo Bonus |
|---|---|
| Winner (multiple) | +40 |
| Winner (once) | +25 |
| Finalist | +15 |
| Semi-finalist | +8 |
| Quarter-finalist | +3 |
| R16 | +1 |
| Group only | 0 |
| First appearance | -10 |

### 5b. Historical Curses (统计规律)
```python
# Defending champion curse: -15 Elo if won previous WC
defending_champions = ['Argentina']  # 2022 winner
curse_elo = -15 if team in defending_champions else 0

# First-time participant penalty
curse_elo += -10 if appearances == 1 else 0

# Host continent advantage for non-host teams from same confederation
# North America -> CONCACAF teams get +5 Elo
```

### 5c. Continental Style Clue
When styles clash, apply small alpha/beta adjustment:
- UEFA vs CAF: UEFA gets +0.02 alpha (structured attacks disorganized defense)
- CONMEBOL vs AFC: CONMEBOL gets +0.03 alpha (creativity vs rigid shape)

---

## Layer 6: Match Context

### Home Advantage
```
if is_host:          gamma = 65  (full home)
elif in_host_country: gamma = 20  (crowd effect)
else:                 gamma = 0   (neutral)

knockout: gamma *= 0.5 if is_host else 0
```

### Stage Goal Multiplier
| Stage | Goal Mult | Draw Shift |
|---|---|---|
| Group MD1 | 1.02 | -0.01 |
| Group MD2 | 1.00 | 0.00 |
| Group MD3 | 0.95 | +0.02 |
| R32 | 0.92 | +0.03 |
| R16 | 0.90 | +0.04 |
| QF | 0.88 | +0.05 |
| SF | 0.85 | +0.06 |
| Final | 0.82 | +0.07 |

---

## Factor Calculation Summary

```python
def predict_wc_match(home, away, context):
    # === Layer 1: Player Elo ===
    squad_h = get_national_squad(home.country)
    squad_a = get_national_squad(away.country)

    player_elo_h = (starting_xi_elo(squad_h) +
                    age_elo(squad_h) +
                    league_elo(squad_h) +
                    cohesion_elo(squad_h) +
                    setpiece_elo(squad_h) +
                    star_bonus(squad_h))
    player_elo_a = (starting_xi_elo(squad_a) +
                    age_elo(squad_a) +
                    league_elo(squad_a) +
                    cohesion_elo(squad_a) +
                    setpiece_elo(squad_a) +
                    star_bonus(squad_a))

    # === Layer 2: Base Elo ===
    elo_h = home.elo_rating + player_elo_h + confederation_adj(home, away)
    elo_a = away.elo_rating + player_elo_a + confederation_adj(away, home)

    # === Layer 3: Decomposition ===
    att_q_h, def_q_h = position_quality(squad_h)
    att_q_a, def_q_a = position_quality(squad_a)
    alpha_h, beta_h = decompose(elo_h, att_q_h, def_q_h)
    alpha_a, beta_a = decompose(elo_a, att_q_a, def_q_a)

    # === Layer 4: Form ===
    form_h = international_form(home)
    form_a = international_form(away)

    # === Layer 5: Tournament ===
    wc_bonus_h = wc_history(home) + historical_curse(home)
    wc_bonus_a = wc_history(away) + historical_curse(away)
    style_adj = continental_style(home.conf, away.conf)

    # === Layer 6: Context ===
    gamma = home_advantage(home, away, context)
    goal_mult, draw_shift = stage_factors(context)

    # === Expected Goals ===
    lam = exp(alpha_h + beta_a + gamma/1000 + style_adj) * goal_mult * (1 + form_h*0.15)
    mu  = exp(alpha_a + beta_h) * goal_mult * (1 + form_a*0.15)
    lam = clamp(lam, 0.15, 4.0)
    mu  = clamp(mu, 0.10, 3.5)

    # === Simulation ===
    rho = -0.15
    result = dc_simulate(lam, mu, rho, n=5000)
    return result
```

---

## Output Format

```python
{
    "home_team": "France", "away_team": "Senegal",
    "stage": "Group I", "matchday": 1,
    "model_version": "wc_v1",

    "expected_goals": {"home": 1.85, "away": 0.72},
    "wdl": {"home_win": 0.62, "draw": 0.21, "away_win": 0.17},
    "score_distribution": {"2-0": 0.15, "1-0": 0.14, ...},
    "most_likely_score": "2-0",
    "over_under": {"over_2_5": 0.42, "under_2_5": 0.58},

    "player_analysis": {
        "home": {
            "starting_xi_score": 86.2,
            "attack_quality": 88.5, "defense_quality": 83.1,
            "squad_depth": 81.3,
            "avg_age": 27.3, "age_score": 0.82,
            "league_quality": 89.5,
            "cohesion": 0.78,
            "set_piece_strength": 0.72,
            "elo_bonus": 95,
            "top_players": ["Mbappe (91)", "Griezmann (86)", "Dembele (85)"]
        },
        "away": { ... }
    },

    "factors": {
        "elo_home": 2005, "elo_away": 1773, "elo_diff": 232,
        "player_elo": {"home": 95, "away": 25},
        "form": {"home": +0.45, "away": -0.12},
        "wc_history": {"home": 40, "away": 8},
        "curse": {"home": -15, "away": 0},
        "home_advantage": 0,
        "cohesion": {"home": 0.78, "away": 0.45},
        "set_piece": {"home": 0.72, "away": 0.55},
        "context": {"stage": "group", "goal_mult": 1.00}
    },

    "simulations": 5000, "duration_ms": 45
}
```

---

## Implementation Plan

### Phase 1: Data Layer
1. `backend/engine/wc_predictor.py` -- Core prediction engine
   - `get_national_squad(country)` -- Query tm_players by country_of_citizenship
   - `calc_player_elo(squad)` -- Starting XI + depth
   - `calc_age_profile(squad)` -- Age distribution
   - `calc_league_quality(squad)` -- League strength
   - `calc_cohesion(squad)` -- League/club concentration
   - `calc_set_piece(squad)` -- Height + GK + scorers
   - `decompose_elo(elo, att_q, def_q)` -- Alpha/beta split
   - `get_international_form(team)` -- Recent results
   - `predict_wc_match(home, away, context)` -- Main entry point

### Phase 2: Simulation
2. `backend/engine/wc_simulator.py` -- Tournament simulator
   - `simulate_group(teams)` -- Monte Carlo group stage
   - `simulate_knockout(bracket)` -- Knockout bracket
   - `simulate_tournament()` -- Full sim -> champion probs

### Phase 3: API
3. `backend/api/worldcup.py` -- REST endpoints
   - `GET /api/worldcup/predict/{match_id}`
   - `POST /api/worldcup/simulate`
   - `GET /api/worldcup/groups`

### Phase 4: Frontend
4. `frontend/src/pages/WorldCup.jsx`
