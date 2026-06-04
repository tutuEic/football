# World Cup Module Design

## Overview

Add a complete FIFA World Cup 2026 module to the football prediction system, covering data ingestion, prediction, tournament simulation, and a dedicated frontend experience.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  WorldCup.jsx                                       │ │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │ │
│  │  │ GroupStage│ │ Bracket  │ │ MatchPredictions   │  │ │
│  │  └──────────┘ └──────────┘ └────────────────────┘  │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │ REST API
┌─────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ api/worldcup │  │engine/wc_    │  │engine/wc_     │  │
│  │   .py        │──│predictor.py  │──│simulator.py   │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │data/pipeline │  │ features/    │                     │
│  │  _wc.py      │  │ elo.py       │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                   MySQL (football_pred)                  │
│  wc_groups  wc_matches  wc_standings  wc_bracket        │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **League code**: `WC2026` — consistent with existing `CL` pattern
2. **Data source**: Football-data.co.uk (primary) + FIFA API fallback + manual seed data
3. **Prediction model**: Adapted Dixon-Coles using FIFA ranking Elo + historical international match data
4. **Tournament format**: 48 teams, 12 groups of 4, then Round of 32 knockout
5. **Match context**: `wc_group`, `wc_knockout`, `wc_round16`, `wc_quarter`, `wc_semi`, `wc_final`

## Database Schema

### wc_groups
| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | Auto increment |
| group_name | VARCHAR(4) | e.g. "A", "B", ..., "L" |
| team | VARCHAR(64) | Team name |
| fifa_ranking | INT | FIFA ranking at draw time |
| elo_rating | FLOAT | Elo rating |

### wc_matches
| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | Auto increment |
| match_num | INT | Match number (1-104) |
| stage | VARCHAR(32) | group, r32, r16, qf, sf, final |
| group_name | VARCHAR(4) | NULL for knockout |
| matchday | INT | Group matchday 1-3 |
| match_date | DATE | |
| match_time | TIME | |
| home_team | VARCHAR(64) | |
| away_team | VARCHAR(64) | |
| home_score | INT | NULL if not played |
| away_score | INT | NULL if not played |
| venue | VARCHAR(128) | Stadium name |
| status | VARCHAR(16) | scheduled, live, finished |
| source | VARCHAR(32) | |

### wc_standings
| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | |
| group_name | VARCHAR(4) | |
| team | VARCHAR(64) | |
| played | INT | |
| wins | INT | |
| draws | INT | |
| losses | INT | |
| goals_for | INT | |
| goals_against | INT | |
| goal_diff | INT | |
| points | INT | |
| position | INT | 1-4 |

### wc_predictions
| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | |
| match_id | INT FK | |
| home_win_prob | FLOAT | |
| draw_prob | FLOAT | |
| away_win_prob | FLOAT | |
| predicted_home_goals | FLOAT | |
| predicted_away_goals | FLOAT | |
| most_likely_score | VARCHAR(8) | |
| confidence | FLOAT | |
| model_version | VARCHAR(16) | |
| created_at | DATETIME | |

## Prediction Engine

### International Team Strength Model

Since we don't have club-level player data for national teams, we use:

1. **FIFA Rankings** → normalized Elo (rankings are already Elo-based since 2018)
2. **Historical WC performance** — past tournament results weighted by recency
3. **Qualifying form** — recent qualifying match results
4. **Friendly results** — lower weight
5. **Squad quality estimate** — based on top-league player count (optional)

### Adapted Dixon-Coles for Internationals

- Home advantage reduced (neutral venues in knockout stages)
- Group stage: home advantage ~30 points Elo (host country gets full 65)
- Knockout: neutral venue, home advantage = 0 (or coin-flip home assignment)
- Rho parameter recalibrated for international football (typically lower-scoring)
- K-factor for Elo updates: higher for WC matches (K=40 vs K=20 for leagues)

## Tournament Simulator

### Group Stage Simulation (Monte Carlo)

For each group of 4 teams:
1. Simulate all 6 matches (home-away is assigned by draw)
2. Calculate points, goal difference, goals for tiebreakers
3. Determine final standings (1st, 2nd qualify; 3rd may qualify in 48-team format)
4. Repeat N=10,000 times → probability of each team finishing in each position

### Knockout Bracket Simulation

After group stage probabilities:
1. For each R32 matchup, compute win probability based on group winner vs runner-up
2. Propagate through bracket: R32 → R16 → QF → SF → Final
3. At each stage, use DC model with `wc_knockout` context
4. Output: probability of each team reaching each stage, winning the tournament

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/worldcup/groups | All group standings |
| GET | /api/worldcup/groups/{name} | Single group detail |
| GET | /api/worldcup/matches | All WC matches (filterable) |
| GET | /api/worldcup/matches/{id} | Single match + prediction |
| GET | /api/worldcup/bracket | Knockout bracket |
| GET | /api/worldcup/predictions | All predictions |
| POST | /api/worldcup/predict/{match_id} | Generate prediction for match |
| POST | /api/worldcup/simulate | Run full tournament simulation |
| GET | /api/worldcup/simulate/result | Get latest simulation result |
| POST | /api/worldcup/refresh | Trigger data refresh |

## Frontend Components

### WorldCup.jsx (Main Page)
Tabbed view with:
1. **Group Stage** — 12 group cards with standings + upcoming matches
2. **Bracket** — Visual knockout bracket (R32 → Final)
3. **Predictions** — Match-by-match predictions with probabilities
4. **Simulation** — Tournament win probabilities chart

### GroupCard.jsx
- Team flags (emoji or CDN)
- P W D L GF GA GD PTS table
- Next match indicator
- Qualification probability bar

### BracketView.jsx
- Visual bracket tree
- Team names filled from group results
- Predicted winners highlighted
- Click to see match prediction detail

## Implementation Order

1. Database schema (SQL migration script)
2. Data pipeline — fetch WC schedule, store in DB
3. Elo integration — use FIFA rankings as initial Elo for national teams
4. WC predictor — adapted DC model for internationals
5. WC simulator — group stage + knockout Monte Carlo
6. API routes — all endpoints
7. Frontend — WorldCup page with all sub-components
8. Register in main.py and App.jsx
