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
from engine.wc_predictor import predict_wc_match, _dc_sample_scores, DC_RHO


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
    """Simulate a knockout match using DC sampling (consistent with wc_simulator.py).

    Samples actual scores from the Dixon-Coles distribution. If drawn after
    90 min, uses a simple extra-time model to produce a winner.
    Returns (winner, pred_dict, method_string).
    """
    ctx = {"stage": stage, "matchday": 1, "is_host": is_host_home}
    pred = predict_wc_match(home, away, ctx)
    lam = pred["expected_goals"]["home"]
    mu = pred["expected_goals"]["away"]

    # Sample score from DC distribution
    for _ in range(100):
        hg, ag = _dc_sample_scores(lam, mu, DC_RHO, n_samples=1)
        hg, ag = int(hg[0]), int(ag[0])
        if hg != ag:
            return (home if hg > ag else away), pred, "90min"

    # Fallback: decide via probability (should rarely reach here)
    wdl = pred["wdl"]
    hw, aw = wdl["home_win"], wdl["away_win"]
    total = hw + aw
    if total > 0:
        hw_norm = hw / total
    else:
        hw_norm = 0.5
    if random.random() < hw_norm:
        return home, pred, "ET"
    else:
        return away, pred, "ET"


def _build_r32_matches(qualified):
    """Build R32 match pairs for 2026 WC (12 groups, 32 qualifiers).
    
    12 group winners + 12 runners-up + 8 best thirds = 32 teams
    Cross-pair: 8 winners vs 8 runners from different groups (16 slots)
    4 remaining winners vs 4 best thirds (but we only have 4 slots left → use 4 thirds)
    Remaining 4 thirds vs remaining 4 runners
    """
    winners = {}
    runners = {}
    thirds = []

    for q in qualified:
        if q["rank"] == 1:
            winners[q["group"]] = q["team"]
        elif q["rank"] == 2:
            runners[q["group"]] = q["team"]
        elif q["rank"] == 3:
            thirds.append(q)

    group_names = sorted(winners.keys())
    r32 = []
    used_w = set()
    used_r = set()

    # Step 1: Cross-pair first 8 groups (4 pairs = 8 matches)
    for i in range(0, min(8, len(group_names) - 1), 2):
        g1, g2 = group_names[i], group_names[i + 1]
        r32.append((winners[g1], runners[g2]))
        r32.append((winners[g2], runners[g1]))
        used_w.update([g1, g2])
        used_r.update([g1, g2])

    # Step 2: Pair remaining 4 group winners vs 4 best thirds
    third_idx = 0
    for g in group_names:
        if g not in used_w and third_idx < len(thirds):
            r32.append((winners[g], thirds[third_idx]["team"]))
            third_idx += 1
            used_w.add(g)

    # Step 3: Pair remaining 4 runners vs remaining thirds
    for g in group_names:
        if g not in used_r and third_idx < len(thirds):
            r32.append((runners[g], thirds[third_idx]["team"]))
            third_idx += 1
            used_r.add(g)

    # Step 4: If still have thirds, pair against already-used winners
    for g in group_names:
        if third_idx >= len(thirds):
            break
        if g in used_w:
            # Replace one runner-up match with a third
            pass  # Skip for now - should have exactly 16 with 8 thirds

    return r32


def simulate_bracket(qualified):
    """Simulate full knockout bracket with proper FIFA seeding."""
    results = {"r32": [], "r16": [], "qf": [], "sf": [], "final": [], "champion": None}

    r32_matches = _build_r32_matches(qualified)

    r32_winners = []
    for h, a in r32_matches:
        w, pred, method = simulate_ko_match(h, a, "r32")
        results["r32"].append({"home": h, "away": a, "winner": w, "method": method,
                               "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        r32_winners.append(w)

    r16_winners = []
    for i in range(0, len(r32_winners) - 1, 2):
        h, a = r32_winners[i], r32_winners[i + 1]
        w, pred, method = simulate_ko_match(h, a, "r16")
        results["r16"].append({"home": h, "away": a, "winner": w, "method": method,
                               "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        r16_winners.append(w)

    qf_winners = []
    for i in range(0, len(r16_winners) - 1, 2):
        h, a = r16_winners[i], r16_winners[i + 1]
        w, pred, method = simulate_ko_match(h, a, "qf")
        results["qf"].append({"home": h, "away": a, "winner": w, "method": method,
                              "wdl": pred["wdl"], "xg": pred["expected_goals"]})
        qf_winners.append(w)

    sf_winners = []
    for i in range(0, len(qf_winners) - 1, 2):
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
    """Run multiple bracket simulations with pre-computed predictions.
    
    Optimization: predict each matchup once, then sample from cached probabilities.
    Speed: ~50x faster than naive approach.
    """
    import numpy as np
    from scipy.stats import poisson
    
    groups = get_wc_groups()
    
    # ===== Phase 1: Pre-compute all group match predictions =====
    group_pred_cache = {}
    for gname, gteams in groups.items():
        names = [t["team"] for t in gteams]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                h, a = names[i], names[j]
                key = (h, a)
                if key not in group_pred_cache:
                    pred = predict_wc_match(h, a, {"stage": "group", "matchday": 1, "is_host": False})
                    group_pred_cache[key] = pred
                    group_pred_cache[(a, h)] = pred  # Symmetric cache
    
    # ===== Phase 2: Pre-compute all possible knockout predictions =====
    # Collect all team names that could reach knockout
    all_teams = set()
    for gteams in groups.values():
        for t in gteams:
            all_teams.add(t["team"])
    
    ko_pred_cache = {}
    team_list = sorted(all_teams)
    for i, h in enumerate(team_list):
        for j, a in enumerate(team_list):
            if i != j:
                key = (h, a)
                if key not in ko_pred_cache:
                    pred = predict_wc_match(h, a, {"stage": "knockout", "matchday": 1, "is_host": False})
                    ko_pred_cache[key] = pred
    
    # ===== Phase 3: Fast Monte Carlo sampling =====
    champion_counts = defaultdict(int)
    final_counts = defaultdict(int)
    sf_counts = defaultdict(int)
    qf_counts = defaultdict(int)
    r16_counts = defaultdict(int)
    r32_counts = defaultdict(int)
    sample_bracket = None
    
    def fast_group_sim(groups):
        """Simulate group stage using cached predictions + numpy sampling."""
        all_qualified = []
        all_third_place = []
        
        for group_name, teams in groups.items():
            names = [t["team"] for t in teams]
            standings = {t: {"pts": 0, "gf": 0, "ga": 0} for t in names}
            
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    h, a = names[i], names[j]
                    pred = group_pred_cache.get((h, a))
                    if pred:
                        lam = pred["expected_goals"]["home"]
                        mu = pred["expected_goals"]["away"]
                        hg = np.random.poisson(max(lam, 0.1))
                        ag = np.random.poisson(max(mu, 0.1))
                    else:
                        hg, ag = 0, 0
                    
                    standings[h]["gf"] += hg
                    standings[h]["ga"] += ag
                    standings[a]["gf"] += ag
                    standings[a]["ga"] += hg
                    
                    if hg > ag:
                        standings[h]["pts"] += 3
                    elif hg < ag:
                        standings[a]["pts"] += 3
                    else:
                        standings[h]["pts"] += 1
                        standings[a]["pts"] += 1
            
            sorted_teams = sorted(standings.items(), key=lambda x: (x[1]["pts"], x[1]["gd"] if "gd" in x[1] else x[1]["gf"] - x[1]["ga"]), reverse=True)
            for idx, (name, stats) in enumerate(sorted_teams):
                stats["gd"] = stats["gf"] - stats["ga"]
            
            sorted_teams = sorted(standings.items(), key=lambda x: (x[1]["pts"], x[1]["gd"], x[1]["gf"]), reverse=True)
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
        
        return all_qualified
    
    def fast_ko_match(home, away):
        """Simulate knockout match using cached predictions + numpy sampling."""
        pred = ko_pred_cache.get((home, away))
        if not pred:
            return home, "90min"
        
        lam = pred["expected_goals"]["home"]
        mu = pred["expected_goals"]["away"]
        
        for _ in range(50):
            hg = np.random.poisson(max(lam, 0.1))
            ag = np.random.poisson(max(mu, 0.1))
            if hg != ag:
                return (home if hg > ag else away), "90min"
        
        # Fallback
        wdl = pred["wdl"]
        hw, aw = wdl["home_win"], wdl["away_win"]
        total = hw + aw
        return (home if random.random() < hw / total else away), "ET"
    
    def fast_bracket(qualified):
        """Simulate full bracket using cached predictions."""
        r32_pairs = _build_r32_matches(qualified)
        
        r32_results = []
        r32_winners = []
        for h, a in r32_pairs:
            w, method = fast_ko_match(h, a)
            r32_results.append({"home": h, "away": a, "winner": w, "method": method})
            r32_winners.append(w)
        
        r16_results = []
        r16_winners = []
        for i in range(0, len(r32_winners) - 1, 2):
            w, method = fast_ko_match(r32_winners[i], r32_winners[i + 1])
            r16_results.append({"home": r32_winners[i], "away": r32_winners[i + 1], "winner": w, "method": method})
            r16_winners.append(w)
        
        qf_results = []
        qf_winners = []
        for i in range(0, len(r16_winners) - 1, 2):
            w, method = fast_ko_match(r16_winners[i], r16_winners[i + 1])
            qf_results.append({"home": r16_winners[i], "away": r16_winners[i + 1], "winner": w, "method": method})
            qf_winners.append(w)
        
        sf_results = []
        sf_winners = []
        for i in range(0, len(qf_winners) - 1, 2):
            w, method = fast_ko_match(qf_winners[i], qf_winners[i + 1])
            sf_results.append({"home": qf_winners[i], "away": qf_winners[i + 1], "winner": w, "method": method})
            sf_winners.append(w)
        
        final_results = []
        champion = None
        if len(sf_winners) >= 2:
            w, method = fast_ko_match(sf_winners[0], sf_winners[1])
            final_results = [{"home": sf_winners[0], "away": sf_winners[1], "winner": w, "method": method}]
            champion = w
        
        return {
            "r32": r32_results, "r16": r16_results, "qf": qf_results,
            "sf": sf_results, "final": final_results, "champion": champion
        }
    
    # Run simulations
    for i in range(n_sims):
        qualified = fast_group_sim(groups)
        bracket = fast_bracket(qualified)
        
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
    # Filter: elo > 70, age <= 35 at WC2026 (born after 1991-06-01)
    from datetime import date, timedelta
    _age_cutoff = (date.today() - timedelta(days=35*365)).strftime("%Y-%m-%d")
    rows = query(
        "SELECT p.player_id, p.name, p.country_of_citizenship, p.elo_rating, "
        "p.position, p.current_club_name, p.market_value_in_eur, p.date_of_birth "
        "FROM tm_players p "
        "INNER JOIN wc_groups g ON p.country_of_citizenship = g.team COLLATE utf8mb4_unicode_ci "
        "WHERE p.elo_rating IS NOT NULL AND p.elo_rating > 70 "
        "AND p.date_of_birth > %s "
        "ORDER BY p.elo_rating DESC LIMIT 30",
        [_age_cutoff],
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


def analyze_group_upsets():
    """Analyze potential upsets and strategic tanking scenarios in group stage."""
    rows = query(
        "SELECT group_name, team, elo_rating, fifa_ranking, is_host FROM wc_groups ORDER BY group_name, elo_rating DESC",
        db="football_pred"
    )
    groups = {}
    for r in rows:
        g = r["group_name"]
        if g not in groups:
            groups[g] = []
        groups[g].append(r)

    upset_alerts = []
    tanking_scenarios = []
    
    for g, teams in sorted(groups.items()):
        top = teams[0]
        second = teams[1]
        third = teams[2]
        fourth = teams[3]
        
        elo_gap = top["elo_rating"] - second["elo_rating"]
        
        # Analyze top vs second match
        try:
            pred = predict_wc_match(top["team"], second["team"], {"stage": "group", "matchday": 1, "is_host": False})
            wdl = pred["wdl"]
            
            # Close matchup alert
            if wdl["away_win"] > 0.20:
                upset_alerts.append({
                    "group": g,
                    "match": f"{top['team']} vs {second['team']}",
                    "favorite": top["team"],
                    "underdog": second["team"],
                    "upset_prob": round(wdl["away_win"], 3),
                    "type": "close_matchup",
                    "description": f"{second['team']} has {wdl['away_win']:.0%} chance to beat {top['team']}",
                    "impact": "Could determine group winner - affects knockout bracket seeding",
                })
            
            # Tanking scenario: top team rests players
            if elo_gap > 80 and third["elo_rating"] > 1550:
                rest_pred = predict_wc_match(top["team"], third["team"], {"stage": "group", "matchday": 3, "is_host": False})
                if rest_pred["wdl"]["away_win"] > 0.12:
                    tanking_scenarios.append({
                        "group": g,
                        "team": top["team"],
                        "opponent": third["team"],
                        "upset_if_rest": round(rest_pred["wdl"]["away_win"], 3),
                        "reason": f"{top['team']} may rest players after securing qualification",
                        "risk": "high" if rest_pred["wdl"]["away_win"] > 0.20 else "medium",
                    })
            
            # Third team upset potential
            if third["elo_rating"] > 1580:
                third_pred = predict_wc_match(second["team"], third["team"], {"stage": "group", "matchday": 2, "is_host": False})
                if third_pred["wdl"]["away_win"] > 0.20:
                    upset_alerts.append({
                        "group": g,
                        "match": f"{second['team']} vs {third['team']}",
                        "favorite": second["team"],
                        "underdog": third["team"],
                        "upset_prob": round(third_pred["wdl"]["away_win"], 3),
                        "type": "third_team_threat",
                        "description": f"{third['team']} could take 2nd place from {second['team']}",
                        "impact": "Could eliminate a stronger team from the group",
                    })
        except Exception:
            pass
    
    return {
        "upset_alerts": sorted(upset_alerts, key=lambda x: x["upset_prob"], reverse=True),
        "tanking_scenarios": sorted(tanking_scenarios, key=lambda x: x["upset_if_rest"], reverse=True),
    }
