# -*- coding: utf-8 -*-
"""
World Cup Tournament Simulator — Monte Carlo
=============================================
Simulates the full 48-team WC2026 tournament:
  - 12 groups of 4 (group stage)
  - Top 2 + 8 best 3rd-place teams advance (32 teams)
  - Knockout bracket: R32 → R16 → QF → SF → Final

Uses wc_predictor.predict_wc_match() for individual match probabilities.
Monte Carlo simulation for tournament-wide probability distributions.
"""
import random
import math
import sys
import os
import time as _time
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_predictor import predict_wc_match, _dc_sample_scores, DC_RHO, _dc_build_sampler, _dc_sample_from_sampler

# ============================================================
# Constants
# ============================================================

# 48-team format: 12 groups, top 2 + 8 best 3rd-place = 32 advance
NUM_GROUPS = 12
TEAMS_PER_GROUP = 4
ADVANCE_TOP_N = 2          # Top 2 from each group
BEST_THIRD_N = 8           # 8 best 3rd-place teams

# Default Monte Carlo iterations
DEFAULT_N_SIMS = 5000


# ============================================================
# Group Stage Simulation
# ============================================================

_groups_cache = None
_groups_cache_time = 0
_GROUPS_TTL = 3600  # 1 hour

def load_groups():
    """Load all WC groups from database (cached for 1 hour)."""
    global _groups_cache, _groups_cache_time
    if _groups_cache is not None and _time.time() - _groups_cache_time < _GROUPS_TTL:
        return _groups_cache
    rows = query(
        "SELECT group_name, team, confederation, fifa_ranking, elo_rating, is_host "
        "FROM wc_groups ORDER BY group_name, fifa_ranking",
        db="football_pred"
    )
    groups = defaultdict(list)
    for r in rows:
        groups[r["group_name"]].append({
            "team": r["team"],
            "confederation": r["confederation"],
            "fifa_ranking": r["fifa_ranking"],
            "elo_rating": r["elo_rating"],
            "is_host": bool(r["is_host"]),
        })
    result = dict(groups)
    _groups_cache = result
    _groups_cache_time = _time.time()
    return result


def load_group_fixtures():
    """Load all group stage fixtures."""
    rows = query(
        "SELECT id, home_team, away_team, match_date "
        "FROM fixtures WHERE league_code = 'WC2026' "
        "ORDER BY match_date, id",
        db="football_pred"
    )
    return rows


def generate_group_schedule(groups):
    """
    Generate round-robin schedule for each group.
    Returns list of (home, away, group) tuples.
    """
    schedule = []
    for group_name, teams in groups.items():
        names = [t["team"] for t in teams]
        # Round-robin: each pair plays once
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                # Assign home/away (first team listed is "home" in the fixture)
                schedule.append((names[i], names[j], group_name))
    return schedule


def simulate_single_group(teams, predictions_cache):
    """
    Simulate one group's 6 matches and return standings.
    teams: list of 4 team dicts
    predictions_cache: dict of (home, away) -> prediction

    Returns: sorted list of team standings.
    """
    names = [t["team"] for t in teams]

    # Initialize standings
    standings = {}
    for name in names:
        standings[name] = {
            "team": name, "played": 0, "wins": 0, "draws": 0, "losses": 0,
            "gf": 0, "ga": 0, "gd": 0, "points": 0,
        }

    # Simulate all 6 matches using pre-computed samplers
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            home, away = names[i], names[j]
            pred = predictions_cache.get((home, away))
            if pred is None:
                pred = predict_wc_match(home, away, {
                    "stage": "group", "matchday": 1,
                    "is_host": any(t["team"] == home and t.get("is_host") for t in teams),
                    "in_host_country": True,
                })
                predictions_cache[(home, away)] = pred

            # Use pre-computed sampler or build one
            sampler_key = f"_sampler_{home}_{away}"
            if sampler_key not in predictions_cache:
                lam = pred["expected_goals"]["home"]
                mu = pred["expected_goals"]["away"]
                probs, n = _dc_build_sampler(lam, mu, DC_RHO)
                predictions_cache[sampler_key] = (probs, n)
            probs, n = predictions_cache[sampler_key]
            hg, ag = _dc_sample_from_sampler(probs, n, n_samples=1)
            hg, ag = int(hg[0]), int(ag[0])

            # Update standings
            standings[home]["played"] += 1
            standings[away]["played"] += 1
            standings[home]["gf"] += hg
            standings[home]["ga"] += ag
            standings[away]["gf"] += ag
            standings[away]["ga"] += hg

            if hg > ag:
                standings[home]["wins"] += 1
                standings[home]["points"] += 3
                standings[away]["losses"] += 1
            elif hg < ag:
                standings[away]["wins"] += 1
                standings[away]["points"] += 3
                standings[home]["losses"] += 1
            else:
                standings[home]["draws"] += 1
                standings[away]["draws"] += 1
                standings[home]["points"] += 1
                standings[away]["points"] += 1

    # Calculate goal difference
    for name in names:
        s = standings[name]
        s["gd"] = s["gf"] - s["ga"]

    # Sort: points desc, GD desc, GF desc, then random
    sorted_standings = sorted(
        standings.values(),
        key=lambda s: (s["points"], s["gd"], s["gf"], random.random()),
        reverse=True,
    )

    return sorted_standings


def get_best_thirds(all_group_standings):
    """
    Select 8 best 3rd-place teams from 12 groups.
    Ranking: points, GD, GF, then fair play (random here).
    """
    thirds = []
    for group_name, standings in all_group_standings.items():
        if len(standings) >= 3:
            third = standings[2].copy()
            third["group"] = group_name
            thirds.append(third)

    # Sort: points desc, GD desc, GF desc
    thirds.sort(key=lambda s: (s["points"], s["gd"], s["gf"], random.random()), reverse=True)

    # Top 8 advance
    advancing = set(t["team"] for t in thirds[:BEST_THIRD_N])
    return advancing


# ============================================================
# Knockout Bracket
# ============================================================

def build_knockout_bracket(group_winners, group_runners_up, best_thirds, groups):
    """
    Build R32 bracket for 48-team FIFA format.
    32 teams = 12 winners + 12 runners-up + 8 best thirds.
    16 R32 matches.

    Per FIFA rules, best thirds are assigned to face specific group winners
    based on which groups the advancing thirds came from. We use the
    simplified bracket: 8 best thirds each face a group winner from
    paired groups, and runners-up fill the remaining slots.
    """
    group_names = sorted(groups.keys())
    r32 = []
    third_teams = list(best_thirds)
    third_idx = 0

    # Process groups in pairs (A-B, C-D, E-F, G-H, I-J, K-L)
    for i in range(0, len(group_names), 2):
        if i + 1 >= len(group_names):
            break
        g1, g2 = group_names[i], group_names[i + 1]
        w1, w2 = group_winners[g1], group_winners[g2]
        r1, r2 = group_runners_up[g1], group_runners_up[g2]

        # Each pair of groups contributes up to 4 R32 matches:
        #   Match 1: Winner G1 vs Runner-up G2
        #   Match 2: Winner G2 vs Runner-up G1
        # If a third from these groups (or assigned slot) qualifies,
        #   Match 3/4: Best third vs Winner from opposite group pair
        r32.append((w1, r2, "r32"))
        r32.append((w2, r1, "r32"))

        # Assign 1-2 best thirds to face group winners from this pair
        # FIFA assigns thirds to specific winner slots; we approximate
        # by giving each pair of groups 1 third match if available.
        if third_idx < len(third_teams):
            # Third faces winner of the "stronger" group in the pair
            if third_idx < len(third_teams):
                r32.append((third_teams[third_idx], w1, "r32") if i % 4 == 0
                           else (w2, third_teams[third_idx], "r32"))
                third_idx += 1

    # Any remaining thirds fill slots against remaining group winners
    used_winners = {m[0] for m in r32} | {m[1] for m in r32}
    remaining_winners = [group_winners[g] for g in group_names
                         if group_winners[g] not in used_winners]
    for tw in remaining_winners:
        if third_idx < len(third_teams):
            r32.append((tw, third_teams[third_idx], "r32"))
            third_idx += 1

    return r32


def simulate_knockout_match(home, away, stage, predictions_cache, squad_cache=None):
    """
    Simulate a knockout match (with extra time / penalties if needed).
    Returns (winner, loser).
    """
    cache_key = (home, away, stage)
    pred = predictions_cache.get(cache_key)
    if pred is None:
        pred = predict_wc_match(home, away, {
            "stage": stage, "is_host": False, "in_host_country": True,
        })
        predictions_cache[cache_key] = pred

    lam = pred["expected_goals"]["home"]
    mu = pred["expected_goals"]["away"]

    # In knockout, if draw after 90 min, we need a winner
    # For simulation, just sample until we get a non-draw
    max_attempts = 100
    for _ in range(max_attempts):
        hg, ag = _dc_sample_scores(lam, mu, DC_RHO, n_samples=1)
        hg, ag = int(hg[0]), int(ag[0])
        if hg != ag:
            return (home, away) if hg > ag else (away, home)

    # Fallback: use probability to decide
    wdl = pred["wdl"]
    r = random.random()
    if r < wdl["home_win"]:
        return home, away
    elif r < wdl["home_win"] + wdl["draw"]:
        # Penalty shootout: 50/50 with slight Elo lean
        return (home, away) if random.random() < 0.5 else (away, home)
    else:
        return away, home


def simulate_knockout_bracket(r32_matches, predictions_cache, squad_cache=None):
    """
    Simulate the full knockout bracket from R32 to Final.
    Returns: dict with results at each stage.
    """
    results = {"r32": [], "r16": [], "qf": [], "sf": [], "final": [], "champion": None}

    # R32
    winners_r32 = []
    for home, away, stage in r32_matches:
        winner, loser = simulate_knockout_match(home, away, "r32", predictions_cache, squad_cache)
        winners_r32.append(winner)
        results["r32"].append({"home": home, "away": away, "winner": winner})

    # R16
    winners_r16 = []
    for i in range(0, len(winners_r32), 2):
        if i + 1 < len(winners_r32):
            winner, _ = simulate_knockout_match(winners_r32[i], winners_r32[i + 1], "r16", predictions_cache, squad_cache)
            winners_r16.append(winner)
            results["r16"].append({"home": winners_r32[i], "away": winners_r32[i + 1], "winner": winner})

    # QF
    winners_qf = []
    for i in range(0, len(winners_r16), 2):
        if i + 1 < len(winners_r16):
            winner, _ = simulate_knockout_match(winners_r16[i], winners_r16[i + 1], "qf", predictions_cache, squad_cache)
            winners_qf.append(winner)
            results["qf"].append({"home": winners_r16[i], "away": winners_r16[i + 1], "winner": winner})

    # SF
    winners_sf = []
    for i in range(0, len(winners_qf), 2):
        if i + 1 < len(winners_qf):
            winner, _ = simulate_knockout_match(winners_qf[i], winners_qf[i + 1], "sf", predictions_cache, squad_cache)
            winners_sf.append(winner)
            results["sf"].append({"home": winners_qf[i], "away": winners_qf[i + 1], "winner": winner})

    # Final
    if len(winners_sf) >= 2:
        champion, runner_up = simulate_knockout_match(winners_sf[0], winners_sf[1], "final", predictions_cache, squad_cache)
        results["final"].append({"home": winners_sf[0], "away": winners_sf[1], "winner": champion})
        results["champion"] = champion

    return results


# ============================================================
# Full Tournament Simulation
# ============================================================

def simulate_tournament(n_sims=DEFAULT_N_SIMS, progress_callback=None):
    """
    Run full Monte Carlo tournament simulation.

    Returns:
        dict with:
        - champion_probs: {team: probability}
        - reach_final: {team: probability}
        - reach_sf: {team: probability}
        - reach_qf: {team: probability}
        - reach_r16: {team: probability}
        - group_advance: {team: probability}
        - group_winners: {team: probability}
        - n_simulations: int
    """
    groups = load_groups()

    # Pre-compute squad analyses for all teams (avoid repeated DB queries)
    from engine.wc_data import analyze_squad
    all_team_names = set()
    for teams in groups.values():
        for t in teams:
            all_team_names.add(t["team"])
    print(f"[SIM] Pre-computing squad analyses for {len(all_team_names)} teams...")
    _squad_cache = {}
    for team_name in all_team_names:
        _squad_cache[team_name] = analyze_squad(team_name)
    print(f"[SIM] Squad analyses cached.")

    # Pre-compute form and base_elo for all teams (skip if functions not available)
    print(f"[SIM] Pre-computing form and base Elo...")
    try:
        from engine.wc_predictor import get_international_form, get_team_base_elo
        for team_name in all_team_names:
            get_international_form(team_name)
            get_team_base_elo(team_name)
    except ImportError:
        print(f"[SIM] Form/Elo pre-compute skipped (functions not available)")
    print(f"[SIM] Form and base Elo cached.")

    # Pre-compute all group match predictions (cache)
    pred_cache = {}
    from engine.wc_predictor import predict_wc_match
    host_teams = {t["team"] for teams in groups.values() for t in teams if t.get("is_host")}
    print(f"[SIM] Pre-computing group match predictions...")
    for gname, gteams in groups.items():
        names = [t["team"] for t in gteams]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                h, a = names[i], names[j]
                pred_cache[(h, a)] = predict_wc_match(h, a, {
                    "stage": "group", "matchday": 1,
                    "is_host": h in host_teams, "in_host_country": True,
                })
    print(f"[SIM] {len(pred_cache)} group predictions cached.")

    # Accumulators
    champion_count = defaultdict(int)
    final_count = defaultdict(int)
    sf_count = defaultdict(int)
    qf_count = defaultdict(int)
    r16_count = defaultdict(int)
    advance_count = defaultdict(int)
    group_winner_count = defaultdict(int)
    group_runner_count = defaultdict(int)

    all_teams = set()
    for teams in groups.values():
        for t in teams:
            all_teams.add(t["team"])

    for sim in range(n_sims):
        if progress_callback and sim % 500 == 0:
            progress_callback(sim, n_sims)

        # --- Group Stage ---
        all_group_standings = {}
        group_winners = {}
        group_runners_up = {}

        for group_name, teams in groups.items():
            standings = simulate_single_group(teams, pred_cache)
            all_group_standings[group_name] = standings

            # Top 2 advance
            group_winners[group_name] = standings[0]["team"]
            group_runners_up[group_name] = standings[1]["team"]
            group_winner_count[standings[0]["team"]] += 1
            group_runner_count[standings[1]["team"]] += 1

            for s in standings[:ADVANCE_TOP_N]:
                advance_count[s["team"]] += 1

        # Best 3rd-place teams
        best_thirds = get_best_thirds(all_group_standings)
        for t in best_thirds:
            advance_count[t] += 1

        # --- Knockout Stage ---
        r32_matches = build_knockout_bracket(
            group_winners, group_runners_up, best_thirds, groups
        )

        ko_results = simulate_knockout_bracket(r32_matches, pred_cache, _squad_cache)

        # Count stage appearances
        for m in ko_results["r32"]:
            r16_count[m["winner"]] += 1
        for m in ko_results["r16"]:
            qf_count[m["winner"]] += 1
        for m in ko_results["qf"]:
            sf_count[m["winner"]] += 1
        for m in ko_results["sf"]:
            final_count[m["winner"]] += 1
        if ko_results["champion"]:
            champion_count[ko_results["champion"]] += 1

    # Convert to probabilities
    def to_probs(counts, total):
        return {team: round(count / total, 4) for team, count in
                sorted(counts.items(), key=lambda x: -x[1])}

    return {
        "champion_probs":    to_probs(champion_count, n_sims),
        "reach_final":       to_probs(final_count, n_sims),
        "reach_sf":          to_probs(sf_count, n_sims),
        "reach_qf":          to_probs(qf_count, n_sims),
        "reach_r16":         to_probs(r16_count, n_sims),
        "group_advance":     to_probs(advance_count, n_sims),
        "group_winner":      to_probs(group_winner_count, n_sims),
        "n_simulations":     n_sims,
    }


def format_simulation_report(result):
    """Format simulation results as a readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"WORLD CUP 2026 SIMULATION — {result['n_simulations']} iterations")
    lines.append("=" * 70)

    lines.append("\n--- CHAMPION PROBABILITY ---")
    for team, prob in list(result["champion_probs"].items())[:15]:
        bar = "#" * int(prob * 100)
        lines.append(f"  {team:20s} {prob:6.1%}  {bar}")

    lines.append("\n--- REACH FINAL ---")
    for team, prob in list(result["reach_final"].items())[:10]:
        lines.append(f"  {team:20s} {prob:6.1%}")

    lines.append("\n--- REACH SEMI-FINAL ---")
    for team, prob in list(result["reach_sf"].items())[:10]:
        lines.append(f"  {team:20s} {prob:6.1%}")

    lines.append("\n--- GROUP ADVANCE PROBABILITY ---")
    for team, prob in list(result["group_advance"].items())[:15]:
        lines.append(f"  {team:20s} {prob:6.1%}")

    return "\n".join(lines)
