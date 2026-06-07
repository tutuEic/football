import json
import math
import sys
import os
sys.path.insert(0, "backend")
from scipy.stats import poisson

with open("wc_historical_clean.json", "r", encoding="utf-8") as f:
    matches = json.load(f)

# Re-classify
for year in [2014, 2018, 2022]:
    year_matches = [m for m in matches if m["year"] == year]
    n = len(year_matches)
    for i, m in enumerate(year_matches):
        if n == 64:
            if i < 48: m["stage"] = "group"
            elif i < 56: m["stage"] = "r16"
            elif i < 60: m["stage"] = "qf"
            elif i < 62: m["stage"] = "sf"
            elif i == 62: m["stage"] = "third"
            else: m["stage"] = "final"

group = [m for m in matches if m.get("stage") == "group"]

# ============================================================
# Backtest: Use Elo-based prediction vs actual results
# ============================================================
# We need team Elo ratings for each year
# For now, use the current wc_groups Elo as proxy (not perfect but reasonable)

from data.mysql_client import query
elo_rows = query("SELECT team, elo_rating FROM wc_groups", db="football_pred")
elo_map = {}
for r in elo_rows:
    elo_map[r["team"]] = float(r["elo_rating"] or 1500)

# Country name mapping (tm_games uses different names than wc_groups)
NAME_MAP = {
    "Korea Republic": "South Korea",
    "USA": "United States",
    "IR Iran": "Iran",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
}

def get_elo(name):
    if name in elo_map:
        return elo_map[name]
    mapped = NAME_MAP.get(name, name)
    if mapped in elo_map:
        return elo_map[mapped]
    return 1500

# Predict group matches using Elo
def predict_from_elo(elo_h, elo_a, rho=-0.10):
    """Predict WDL from Elo difference using DC model."""
    diff = elo_h - elo_a
    # Elo to expected goals
    lam = max(0.3, 1.3 + diff / 800)
    mu = max(0.2, 1.1 - diff / 800)
    
    # DC probabilities
    max_goals = 8
    n = max_goals + 1
    prob_h, prob_d, prob_a = 0, 0, 0
    for i in range(n):
        for j in range(n):
            p = poisson.pmf(i, lam) * poisson.pmf(j, mu)
            if i == 0 and j == 0:
                tau = max(1 - lam * mu * rho, 1e-10)
            elif i == 0 and j == 1:
                tau = 1 + lam * rho
            elif i == 1 and j == 0:
                tau = 1 + mu * rho
            elif i == 1 and j == 1:
                tau = max(1 - rho, 1e-10)
            else:
                tau = 1.0
            p = max(tau * p, 0)
            if i > j: prob_h += p
            elif i == j: prob_d += p
            else: prob_a += p
    
    total = prob_h + prob_d + prob_a
    return prob_h/total, prob_d/total, prob_a/total

# Backtest on group stage
correct_old = 0  # Using rho=-0.10
correct_new = 0  # Using rho=+0.10
correct_weighted = 0  # Using weighted Elo
total = 0
brier_old = 0
brier_new = 0

for m in group:
    elo_h = get_elo(m["home"])
    elo_a = get_elo(m["away"])
    
    # Old model (rho=-0.10)
    ph_old, pd_old, pa_old = predict_from_elo(elo_h, elo_a, rho=-0.10)
    pred_old = "H" if ph_old > max(pd_old, pa_old) else "D" if pd_old > pa_old else "A"
    
    # New calibrated (rho=+0.10)
    ph_new, pd_new, pa_new = predict_from_elo(elo_h, elo_a, rho=+0.10)
    pred_new = "H" if ph_new > max(pd_new, pa_new) else "D" if pd_new > pa_new else "A"
    
    actual = m["result"]
    
    if pred_old == actual: correct_old += 1
    if pred_new == actual: correct_new += 1
    
    # Brier score
    actual_vec = {"H": (1,0,0), "D": (0,1,0), "A": (0,0,1)}[actual]
    brier_old += (ph_old - actual_vec[0])**2 + (pd_old - actual_vec[1])**2 + (pa_old - actual_vec[2])**2
    brier_new += (ph_new - actual_vec[0])**2 + (pd_new - actual_vec[1])**2 + (pa_new - actual_vec[2])**2
    
    total += 1

print("=== Backtest on 144 WC Group Stage Matches (2014-2022) ===")
print()
print("Old model (rho=-0.10):")
print("  Accuracy: " + str(round(correct_old/total*100, 1)) + "%")
print("  Brier: " + str(round(brier_old/total, 4)))
print()
print("New calibrated (rho=+0.10):")
print("  Accuracy: " + str(round(correct_new/total*100, 1)) + "%")
print("  Brier: " + str(round(brier_new/total, 4)))

# Also test different rho values
print()
print("=== Rho Sensitivity ===")
for rho in [-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15]:
    c = 0
    b = 0
    for m in group:
        elo_h = get_elo(m["home"])
        elo_a = get_elo(m["away"])
        ph, pd, pa = predict_from_elo(elo_h, elo_a, rho=rho)
        pred = "H" if ph > max(pd, pa) else "D" if pd > pa else "A"
        if pred == m["result"]: c += 1
        av = {"H": (1,0,0), "D": (0,1,0), "A": (0,0,1)}[m["result"]]
        b += (ph - av[0])**2 + (pd - av[1])**2 + (pa - av[2])**2
    acc = round(c/total*100, 1)
    br = round(b/total, 4)
    marker = " <-- current" if abs(rho + 0.10) < 0.01 else (" <-- calibrated" if abs(rho - 0.10) < 0.01 else "")
    print("  rho=" + str(round(rho, 2)) + ": Acc=" + str(acc) + "% Brier=" + str(br) + marker)

# ============================================================
# Draw rate analysis
# ============================================================
print()
print("=== Draw Rate: Model vs Actual ===")
actual_draws = sum(1 for m in group if m["result"] == "D") / len(group)
print("Actual draw rate: " + str(round(actual_draws*100, 1)) + "%")

for rho in [-0.10, 0.0, 0.10]:
    model_draws = 0
    for m in group:
        elo_h = get_elo(m["home"])
        elo_a = get_elo(m["away"])
        _, pd, _ = predict_from_elo(elo_h, elo_a, rho=rho)
        model_draws += pd
    avg_draw = model_draws / len(group)
    print("  rho=" + str(round(rho, 2)) + ": Model avg draw = " + str(round(avg_draw*100, 1)) + "%")
