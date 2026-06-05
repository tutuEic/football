# -*- coding: utf-8 -*-
"""
Knockout Bracket Simulation for WC2026.
Simulates from Round of 32 to Final with Golden Ball prediction.
"""
import sys
import os
import random
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mysql_client import query
from engine.wc_predictor import predict_wc_match


def get_wc_groups():
    """Get all WC2026 groups with teams."""
    rows = query(
        "SELECT group_name, team, fifa_ranking, elo_rating, is_host FROM wc_groups ORDER BY group_name, fifa_ranking",
        db="football_pred"
    )
    groups = {}
    for r in rows:
        g = r["group_name"]
        if g not in groups:
            groups[g] = []
        groups[g].append({
            "team": r["team"],
            "fifa_ranking": r["fifa_ranking"],
            "elo_rating": r["elo_rating"],
            "is_host": bool(r["is_host"]),
        })
    return groups


def simulate_group_stage(groups):
    """Simulate group stage and return qualifiers."""
    all_qualified = []
    all_third_place = []

    for group_name, teams in groups.items():
        standings = {t["team"]: {"pts": 0, "gf": 0, "ga": 0} for t in teams}

        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                home = teams[i]
                away = teams[j]
                ctx = {"stage": "group", "matchday": 1, "is_host": home["is_host"]}
                pred = predict_wc_match(home["team"], away["team"], ctx)
                wdl = pred["wdl"]
                xg = pred["expected_goals"]

                r = random.random()
                if r < wdl["home_win"]:
                    standings[home["team"]]["pts"] += 3
                elif r < wdl["home_win"] + wdl["draw"]:
                    standings[home["team"]]["pts"] += 1
                    standings[away["team"]]["pts"] += 1
                else:
                    standings[away["team"]]["pts"] += 3

                hg = max(0, int(random.gauss(xg["home"], 1.0)))
                ag = max(0, int(random.gauss(xg["away"], 1.0)))
                standings[home["team"]]["gf"] += hg
                standings[home["team"]]["ga"] += ag
                standings[away["team"]]["gf"] += ag
                standings[away["team"]]["ga"] += hg

        for t in standings:
            standings[t]["gd"] = standings[t]["gf"] - standings[t]["ga"]

        sorted_teams = sorted(
            standings.items(),
            key=lambda x: (x[1]["pts"], x[1]["gd"], x[1]["gf"]),
            reverse=True,
        )

        all_qualified.append({"team": sorted_teams[0][0], "group": group_name, "rank": 1})
        all_qualified.append({"team": sorted_teams[1][0], "group": group_name, "rank": 2})
        all_third_place.append({
            "team": sorted_teams[2][0], "group": group_name,
            "pts": sorted_teams[2][1]["pts"],
            "gd": sorted_teams[2][1]["gd"],
            "gf": sorted_teams[2][1]["gf"],
        })

    all_third_place.sort(key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)
    for t in all_third_place[:8]:
        all_qualified.append({"team": t["team"], "group": t["group"], "rank": 3})

    return all_qualified, all_third_place


def simulate_ko_match(home, away, stage, is_host_home=False):
    """Simulate a knockout match."""
    ctx = {"stage": stage, "matchday": 1, "is_host": is_host_home}
    pred = predict_wc_match(home, away, ctx)
    wdl = pred["wdl"]

    r = random.random()
    if r < wdl["home_win"]:
        return home, pred, "90min"
    elif r < wdl["home_win"] + wdl["draw"]:
        # Extra time
        et_home = wdl["home_win"] + wdl["draw"] * 0.4
        et_away = wdl["away_win"] + wdl["draw"] * 0.4
        r2 = random.random()
        if r2 < et_home:
            return home, pred, "ET"
        elif r2 < et_home + wdl["draw"] * 0.2:
            pen_home = 0.5 + (wdl["home_win"] - wdl["away_win"]) * 0.2
            return (home if random.random() < pen_home else away), pred, "Penalties"
        else:
            return away, pred, "ET"
    else:
        return away, pred, "90min"


def simulate_bracket(qualified):
    """Simulate full knockout bracket."""
    results = {"r32": [], "r16": [], "qf": [], "sf": [], "final": [], "champion": None}
    random.shuffle(qualified)

    r32_winners = []
    for i in range(0, 32, 2):
        if i + 1 < len(qualified):
            h, a = qualified[i]["team"], qualified[i + 1]["team"]
            w, pred, method = simulate_ko_match(h, a, "r32")
            results["r32"].append({"home": h, "away": a, "winner": w, "method": method,
                                   "wdl": pred["wdl"], "xg": pred["expected_goals"]})
            r32_winners.append(w)

    r16_winners = []
    for i in range(0, len(r32_winners), 2):
        h, a = r32_winners[i], r32_winners[i + 1]
        w, pred, method = simulate_ko_match(h, a, "r16")
        results["r16"].append({"home": h, "away": a, "winner": w, "method": method,
                               "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        r16_winners.append(w)

    qf_winners = []
    for i in range(0, len(r16_winners), 2):
        h, a = r16_winners[i], r16_winners[i + 1]
        w, pred, method = simulate_ko_match(h, a, "qf")
        results["qf"].append({"home": h, "away": a, "winner": w, "method": method,
                              "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        qf_winners.append(w)

    sf_winners = []
    for i in range(0, len(qf_winners), 2):
        h, a = qf_winners[i], qf_winners[i + 1]
        w, pred, method = simulate_ko_match(h, a, "sf")
        results["sf"].append({"home": h, "away": a, "winner": w, "method": method,
                              "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        sf_winners.append(w)

    if len(sf_winners) >= 2:
        h, a = sf_winners[0], sf_winners[1]
        w, pred, method = simulate_ko_match(h, a, "final")
        results["final"].append({"home": h, "away": a, "winner": w, "method": method,
                                 "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        results["champion"] = w

    return results


def simulate_bracket_n_times(n_sims=100):
    """Run multiple bracket simulations and aggregate results."""
    groups = get_wc_groups()

    champion_counts = defaultdict(int)
    final_counts = defaultdict(int)
    sf_counts = defaultdict(int)
    qf_counts = defaultdict(int)
    r16_counts = defaultdict(int)
    r32_counts = defaultdict(int)
    sample_bracket = None

    for i in range(n_sims):
        qualified, _ = simulate_group_stage(groups)
        bracket = simulate_bracket(qualified)

        if sample_bracket is None:
            sample_bracket = bracket

        if bracket["champion"]:
            champion_counts[bracket["champion"]] += 1
        for m in bracket["final"]:
            for t in [m["home"], m["away"]]:
                final_counts[t] += 1
        for m in bracket["sf"]:
            for t in [m["home"], m["away"]]:
                sf_counts[t] += 1
        for m in bracket["qf"]:
            for t in [m["home"], m["away"]]:
                qf_counts[t] += 1
        for m in bracket["r16"]:
            for t in [m["home"], m["away"]]:
                r16_counts[t] += 1
        for m in bracket["r32"]:
            for t in [m["home"], m["away"]]:
                r32_counts[t] += 1

    def to_probs(counts, total):
        return sorted(
            [{"team": t, "prob": round(c / total, 4)} for t, c in counts.items()],
            key=lambda x: x["prob"], reverse=True,
        )

    return {
        "n_simulations": n_sims,
        "champion_probs": to_probs(champion_counts, n_sims)[:15],
        "reach_final": to_probs(final_counts, n_sims)[:15],
        "reach_sf": to_probs(sf_counts, n_sims)[:15],
        "reach_qf": to_probs(qf_counts, n_sims)[:15],
        "sample_bracket": sample_bracket,
    }


def get_golden_ball_candidates():
    """Get Golden Ball candidates based on player Elo and team strength."""
    rows = query(
        "SELECT p.player_id, p.name, p.country_of_citizenship, p.elo_rating, "
        "p.position, p.current_club_name, p.market_value_in_eur "
        "FROM tm_players p "
        "INNER JOIN wc_groups g ON p.country_of_citizenship = g.team COLLATE utf8mb4_unicode_ci "
        "WHERE p.elo_rating IS NOT NULL AND p.elo_rating > 70 "
        "ORDER BY p.elo_rating DESC LIMIT 30",
        db="football_pred",
    )
    candidates = []
    for r in rows:
        candidates.append({
            "player": r["name"],
            "team": r["country_of_citizenship"],
            "elo": r["elo_rating"],
            "position": r["position"],
            "club": r["current_club_name"],
            "market_value": r["market_value_in_eur"],
        })
    return candidates
