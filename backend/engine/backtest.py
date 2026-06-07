"""Docstring."""
from engine.dixon_coles import DixonColes
from data.match_repo import get_matches_for_training, get_seasons
import numpy as np


def backtest(league_code, test_season, train_window=2):
    """Docstring."""
    all_seasons = get_seasons(league_code)
    all_seasons.sort()

    #  鎵惧埌娴嬭瘯璧涘鐨勭储寮?
    try:
        test_idx = all_seasons.index(test_season)
    except ValueError:
        return {"error": f"Season {test_season} not found for {league_code}"}

    start_idx = max(0, test_idx - train_window)
    train_seasons = all_seasons[start_idx:test_idx]

    if len(train_seasons) < 1:
        return {"error": f"No prior seasons to train on (need at least 1 before {test_season})"}

    print(f"Backtest: {league_code} 鈥?train on {train_seasons}, test on {test_season}")

    # 璁粌
    train_matches = get_matches_for_training(league_code, train_seasons)
    if len(train_matches) < 30:
        return {"error": f"Only {len(train_matches)} training matches (need >= 30)"}

    model = DixonColes()
    success = model.fit(train_matches)
    if not success:
        return {"error": "Model training failed"}

    # 娴嬭瘯
    test_matches = get_matches_for_training(league_code, [test_season])
    if not test_matches:
        return {"error": f"No test matches for {league_code} {test_season}"}

    correct = 0
    brier_sum = 0
    per_outcome = {"H": {"correct": 0, "total": 0}, "D": {"correct": 0, "total": 0}, "A": {"correct": 0, "total": 0}}

    for m in test_matches:
        try:
            probs = model.get_match_probs(m["home"], m["away"])
        except Exception:
            continue

        # 瀹為檯缁撴灉
        hg, ag = m["home_goals"], m["away_goals"]
        if hg > ag:
            actual = "H"
            actual_prob = probs["home_win"]
        elif ag > hg:
            actual = "A"
            actual_prob = probs["away_win"]
        else:
            actual = "D"
            actual_prob = probs["draw"]

        outcomes = {"H": probs["home_win"], "D": probs["draw"], "A": probs["away_win"]}
        predicted = max(outcomes, key=outcomes.get)

        per_outcome[actual]["total"] += 1
        if predicted == actual:
            correct += 1
            per_outcome[actual]["correct"] += 1

        # Brier Score: 危(pred_prob - actual_onehot)虏 / 3
        brier_sum += (probs["home_win"] - (1 if actual == "H" else 0)) ** 2
        brier_sum += (probs["draw"] - (1 if actual == "D" else 0)) ** 2
        brier_sum += (probs["away_win"] - (1 if actual == "A" else 0)) ** 2

    n = len(test_matches)
    accuracy = correct / n

    # Calibration analysis: group predictions into bins
    cal_bins = {}
    bin_edges = [0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 1.0]
    for i in range(len(bin_edges) - 1):
        cal_bins[f"{bin_edges[i]:.0%}-{bin_edges[i+1]:.0%}"] = {"predicted": [], "actual": []}

    for m in test_matches:
        try:
            probs = model.get_match_probs(m["home"], m["away"])
        except Exception:
            continue
        outcomes = {"H": probs["home_win"], "D": probs["draw"], "A": probs["away_win"]}
        predicted_prob = max(outcomes.values())
        predicted_outcome = max(outcomes, key=outcomes.get)
        hg, ag = m["home_goals"], m["away_goals"]
        actual = "H" if hg > ag else ("A" if ag > hg else "D")
        is_correct = 1.0 if predicted_outcome == actual else 0.0

        # Find the right bin
        for label in cal_bins:
            parts = label.replace(" ", "").split("-")
            lo_str = parts[0].strip()
            hi_str = parts[1].strip()
            lo_f = float(lo_str.strip("%")) / 100 if "%" in lo_str else float(lo_str)
            hi_f = float(hi_str.strip("%")) / 100 if "%" in hi_str else float(hi_str)
            if lo_f <= predicted_prob < hi_f or (hi_f == 1.0 and predicted_prob == 1.0):
                cal_bins[label]["predicted"].append(predicted_prob)
                cal_bins[label]["actual"].append(is_correct)
                break

    calibration = []
    for label, data in cal_bins.items():
        if data["predicted"]:
            avg_pred = sum(data["predicted"]) / len(data["predicted"])
            avg_actual = sum(data["actual"]) / len(data["actual"])
            calibration.append({
                "bin": label,
                "avg_predicted": round(avg_pred, 3),
                "avg_actual": round(avg_actual, 3),
                "count": len(data["predicted"]),
                "calibration_error": round(abs(avg_pred - avg_actual), 3),
            })
    brier = brier_sum / (n * 3)  # 闄や互 3 涓被鍒?
    return {
        "league": league_code,
        "train_seasons": train_seasons,
        "train_matches": len(train_matches),
        "test_season": test_season,
        "test_matches": n,
        "accuracy": round(accuracy, 4),
        "brier_score": round(brier, 4),
        "correct": correct,
        "total": n,
        "calibration": calibration,
        "per_outcome": {
            "home": {
                "total": per_outcome["H"]["total"],
                "correct": per_outcome["H"]["correct"],
                "accuracy": round(per_outcome["H"]["correct"] / max(per_outcome["H"]["total"], 1), 3),
            },
            "draw": {
                "total": per_outcome["D"]["total"],
                "correct": per_outcome["D"]["correct"],
                "accuracy": round(per_outcome["D"]["correct"] / max(per_outcome["D"]["total"], 1), 3),
            },
            "away": {
                "total": per_outcome["A"]["total"],
                "correct": per_outcome["A"]["correct"],
                "accuracy": round(per_outcome["A"]["correct"] / max(per_outcome["A"]["total"], 1), 3),
            },
        },
    }


def run_league_backtests(league_code, max_seasons=3):
    """Run backtests for the most recent seasons of a league."""
    all_seasons = get_seasons(league_code)
    all_seasons.sort()
    test_seasons = all_seasons[-max_seasons:] if len(all_seasons) > max_seasons else all_seasons[1:]
    results = []
    for s in test_seasons:
        try:
            r = backtest(league_code, s)
            if "error" not in r:
                results.append(r)
        except Exception:
            pass
    return results


def compare_leagues(league_codes=None, test_season=None):
    """Compare backtest results across leagues."""
    if league_codes is None:
        from data.match_repo import get_all_leagues
        league_codes = get_all_leagues()[:5]
    summary = {}
    for lc in league_codes:
        try:
            if test_season:
                r = backtest(lc, test_season)
                if "error" not in r:
                    summary[lc] = {"accuracy": r["accuracy"], "brier_score": r["brier_score"], "test_matches": r["test_matches"]}
            else:
                results = run_league_backtests(lc)
                if results:
                    accs = [r["accuracy"] for r in results if "accuracy" in r]
                    briers = [r["brier_score"] for r in results if "brier_score" in r]
                    if accs:
                        summary[lc] = {"avg_accuracy": round(float(np.mean(accs)), 3), "avg_brier": round(float(np.mean(briers)), 3), "tests": len(accs)}
        except Exception as e:
            summary[lc] = {"error": str(e)}
    return summary


def betting_backtest(league_code, test_season, train_window=2, stake=1.0, min_ev=0.0):
    """Simulate flat-stake betting using DC model vs market odds. Returns ROI by odds bucket."""
    all_seasons = get_seasons(league_code)
    all_seasons.sort()
    try:
        test_idx = all_seasons.index(test_season)
    except ValueError:
        return {"error": f"Season {test_season} not found"}

    start_idx = max(0, test_idx - train_window)
    train_seasons = all_seasons[start_idx:test_idx]

    from data.mysql_client import query
    test_data = query("""
        SELECT m.home_team, m.away_team, m.ftr,
               o.avgh, o.avgd, o.avga
        FROM matches m
        LEFT JOIN odds o ON m.id = o.match_id
        WHERE m.league_code = %s AND m.season = %s
          AND m.fthg IS NOT NULL AND o.avgh IS NOT NULL
    """, [league_code, test_season])

    if not test_data:
        return {"error": "No matches with odds found"}

    train_matches = get_matches_for_training(league_code, train_seasons)
    model = DixonColes()
    model.fit(train_matches)

    bets = []
    total_staked = 0.0
    total_return = 0.0

    for m in test_data:
        try:
            probs = model.get_match_probs(m["home_team"], m["away_team"])
        except Exception:
            continue
        actual = m["ftr"]
        if actual not in ("H", "D", "A"):
            continue

        for outcome, prob_key, odds_key in [
            ("H", "home_win", "avgh"), ("D", "draw", "avgd"), ("A", "away_win", "avga"),
        ]:
            prob = probs[prob_key]
            odds = float(m[odds_key] or 0)
            if odds <= 1.0:
                continue
            ev = prob * odds - 1
            if ev > min_ev:
                won = (actual == outcome)
                total_staked += stake
                total_return += stake * odds if won else 0
                bets.append({
                    "match": f"{m['home_team']} vs {m['away_team']}",
                    "outcome": outcome, "model_prob": round(prob, 4),
                    "market_odds": round(odds, 2), "ev": round(ev, 4),
                    "actual": actual, "won": won,
                    "pnl": round(stake * (odds - 1) if won else -stake, 2),
                    "bucket": _odds_bucket(odds),
                })

    if not bets:
        return {"error": "No bets placed", "min_ev": min_ev}

    buckets = {}
    for b in bets:
        bk = b["bucket"]
        if bk not in buckets:
            buckets[bk] = {"bets": 0, "wins": 0, "staked": 0.0, "returned": 0.0}
        buckets[bk]["bets"] += 1
        buckets[bk]["staked"] += stake
        if b["won"]:
            buckets[bk]["wins"] += 1
            buckets[bk]["returned"] += stake * b["market_odds"]
    for bk in buckets:
        b = buckets[bk]
        b["win_rate"] = round(b["wins"] / b["bets"], 3) if b["bets"] else 0
        b["roi"] = round((b["returned"] - b["staked"]) / b["staked"], 4) if b["staked"] else 0

    return {
        "league": league_code, "test_season": test_season, "train_seasons": train_seasons,
        "betting": {
            "total_bets": len(bets),
            "wins": sum(1 for b in bets if b["won"]),
            "win_rate": round(sum(1 for b in bets if b["won"]) / len(bets), 3),
            "staked": round(total_staked, 2), "returned": round(total_return, 2),
            "profit": round(total_return - total_staked, 2),
            "roi": round((total_return - total_staked) / total_staked, 4) if total_staked else 0,
            "min_ev": min_ev, "by_bucket": buckets,
            "top_bets": sorted(bets, key=lambda x: -x["ev"])[:10],
        },
    }


def _odds_bucket(odds):
    if odds < 1.5: return "1.0-1.5 (heavy fav)"
    elif odds < 2.0: return "1.5-2.0 (fav)"
    elif odds < 3.0: return "2.0-3.0 (moderate)"
    elif odds < 5.0: return "3.0-5.0 (underdog)"
    else: return "5.0+ (longshot)"



def compare_model_versions(league_code, test_season, train_window=2, min_ev=0.0):
    """Compare standard DC vs time-weighted DC on the same test set.
    
    Returns side-by-side accuracy, Brier score, and betting ROI.
    """
    import math
    from datetime import datetime, date
    from data.mysql_client import query

    all_seasons = get_seasons(league_code)
    all_seasons.sort()
    try:
        test_idx = all_seasons.index(test_season)
    except ValueError:
        return {"error": f"Season {test_season} not found"}

    start_idx = max(0, test_idx - train_window)
    train_seasons = all_seasons[start_idx:test_idx]

    # Get test matches with odds
    test_data = query("""
        SELECT m.home_team, m.away_team, m.fthg, m.ftag, m.ftr,
               o.avgh, o.avgd, o.avga
        FROM matches m
        LEFT JOIN odds o ON m.id = o.match_id
        WHERE m.league_code = %s AND m.season = %s
          AND m.fthg IS NOT NULL AND o.avgh IS NOT NULL
    """, [league_code, test_season])

    if not test_data:
        return {"error": "No test data with odds"}

    # Train standard DC
    train_matches = get_matches_for_training(league_code, train_seasons)
    std_model = DixonColes()
    std_model.fit(train_matches)

    # Train time-weighted DC
    today = date.today()
    dated = query(f"""
        SELECT home_team AS home, away_team AS away,
               fthg AS home_goals, ftag AS away_goals, match_date
        FROM matches
        WHERE league_code=%s AND season IN ({','.join(['%s']*len(train_seasons))})
          AND fthg IS NOT NULL AND ftag IS NOT NULL
    """, [league_code] + list(train_seasons))

    weighted = []
    for m in dated:
        md = m.get('match_date')
        if md:
            if isinstance(md, str):
                md = datetime.strptime(md, '%Y-%m-%d').date()
            days_ago = (today - md).days
        else:
            days_ago = 180
        weighted.append({**m, 'weight': round(math.exp(-0.5 * days_ago / 365), 4)})

    tw_model = DixonColes()
    tw_model.fit(weighted[-500:] if len(weighted) > 500 else weighted)

    # Evaluate both
    def eval_model(model, name):
        correct = 0
        brier = 0.0
        bets = 0
        wins = 0
        staked = 0.0
        returned = 0.0

        for m in test_data:
            try:
                probs = model.get_match_probs(m["home_team"], m["away_team"])
            except Exception:
                continue
            actual = m["ftr"]
            if actual not in ("H", "D", "A"):
                continue

            outcomes = {"H": probs["home_win"], "D": probs["draw"], "A": probs["away_win"]}
            predicted = max(outcomes, key=outcomes.get)
            if predicted == actual:
                correct += 1

            brier += (probs["home_win"] - (1 if actual == "H" else 0)) ** 2
            brier += (probs["draw"] - (1 if actual == "D" else 0)) ** 2
            brier += (probs["away_win"] - (1 if actual == "A" else 0)) ** 2

            for outcome, prob_key, odds_key in [
                ("H", "home_win", "avgh"), ("D", "draw", "avgd"), ("A", "away_win", "avga"),
            ]:
                ev = probs[prob_key] * float(m[odds_key] or 0) - 1
                if ev > min_ev and float(m[odds_key] or 0) > 1.0:
                    bets += 1
                    staked += 1.0
                    if actual == outcome:
                        wins += 1
                        returned += float(m[odds_key])

        n = len(test_data)
        return {
            "model": name, "matches": n,
            "accuracy": round(correct / n, 4) if n else 0,
            "brier_score": round(brier / (n * 3), 4) if n else 0,
            "bets": bets, "wins": wins,
            "roi": round((returned - staked) / staked, 4) if staked else 0,
        }

    std_result = eval_model(std_model, "standard_dc")
    tw_result = eval_model(tw_model, "time_weighted_dc")

    return {
        "league": league_code, "test_season": test_season,
        "train_seasons": train_seasons,
        "min_ev": min_ev,
        "standard": std_result,
        "time_weighted": tw_result,
        "improvement": {
            "accuracy_delta": round(tw_result["accuracy"] - std_result["accuracy"], 4),
            "brier_delta": round(tw_result["brier_score"] - std_result["brier_score"], 4),
            "roi_delta": round(tw_result["roi"] - std_result["roi"], 4),
        },
    }
