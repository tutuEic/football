"""Test wc_predictor.py — verify 6-layer prediction engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.wc_predictor import (
    predict_wc_match, predict_all_group_matches,
    decompose_elo, get_international_form,
    get_wc_history_bonus, get_historical_curse,
)

# ============================================================
# Test 1: Single match prediction — France vs Brazil
# ============================================================
print("=" * 70)
print("TEST 1: France vs Brazil (Group Stage)")
print("=" * 70)

pred = predict_wc_match("France", "Brazil", {
    "stage": "group", "matchday": 1, "is_host": False, "in_host_country": True
})

print(f"  Expected goals:  {pred['expected_goals']}")
print(f"  WDL:             {pred['wdl']}")
print(f"  Most likely:     {pred['most_likely_score']} ({pred['most_likely_prob']:.1%})")
print(f"  Over/Under 2.5:  {pred['over_under']}")
print(f"  Confidence:      {pred['confidence']}")

print(f"\n  Elo factors:")
f = pred["factors"]
print(f"    FIFA Elo:    H={f['elo']['home_fifa']} A={f['elo']['away_fifa']}")
print(f"    Player Elo:  H={f['elo']['player_elo']['home']} A={f['elo']['player_elo']['away']}")
print(f"    Conf adj:    {f['elo']['conf_adj']}")
print(f"    Combined:    H={f['elo']['combined']['home']} A={f['elo']['combined']['away']}")
print(f"    Diff:        {f['elo']['diff']}")
print(f"  Decomposition: {f['decomposition']}")
print(f"  Form:          {f['form']}")
print(f"  Tournament:    {f['tournament']}")
print(f"  Context:       {f['context']}")

print(f"\n  France top players: {pred['player_analysis']['home']['top_players']}")
print(f"  Brazil top players: {pred['player_analysis']['away']['top_players']}")

# ============================================================
# Test 2: Host advantage — Mexico vs Czechia
# ============================================================
print("\n" + "=" * 70)
print("TEST 2: Mexico (host) vs Czechia")
print("=" * 70)

pred2 = predict_wc_match("Mexico", "Czechia", {
    "stage": "group", "matchday": 1, "is_host": True, "in_host_country": True
})

print(f"  Expected goals:  {pred2['expected_goals']}")
print(f"  WDL:             {pred2['wdl']}")
print(f"  Most likely:     {pred2['most_likely_score']}")
print(f"  Home advantage:  {pred2['factors']['context']['home_advantage_gamma']}")

# ============================================================
# Test 3: Knockout match — England vs Germany (QF)
# ============================================================
print("\n" + "=" * 70)
print("TEST 3: England vs Germany (Quarter-Final)")
print("=" * 70)

pred3 = predict_wc_match("England", "Germany", {
    "stage": "qf", "is_host": False, "in_host_country": True
})

print(f"  Expected goals:  {pred3['expected_goals']}")
print(f"  WDL:             {pred3['wdl']}")
print(f"  Most likely:     {pred3['most_likely_score']}")
print(f"  Elo diff:        {pred3['factors']['elo']['diff']}")

# ============================================================
# Test 4: David vs Goliath — Argentina vs Jordan
# ============================================================
print("\n" + "=" * 70)
print("TEST 4: Argentina vs Jordan (Group)")
print("=" * 70)

pred4 = predict_wc_match("Argentina", "Jordan", {
    "stage": "group", "matchday": 1, "is_host": False, "in_host_country": True
})

print(f"  Expected goals:  {pred4['expected_goals']}")
print(f"  WDL:             {pred4['wdl']}")
print(f"  Most likely:     {pred4['most_likely_score']}")
print(f"  Elo diff:        {pred4['factors']['elo']['diff']}")

# ============================================================
# Test 5: International form check
# ============================================================
print("\n" + "=" * 70)
print("TEST 5: International Form")
print("=" * 70)

for team in ["France", "Brazil", "England", "Argentina", "Germany", "Japan"]:
    form = get_international_form(team)
    print(f"  {team:15s} form={form:+.3f}")

# ============================================================
# Test 6: Validation
# ============================================================
print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)

errors = []

# Check probabilities sum to ~1
wdl_sum = sum(pred["wdl"].values())
if abs(wdl_sum - 1.0) > 0.02:
    errors.append(f"WDL sum = {wdl_sum:.4f}, expected ~1.0")

# Check host advantage
if pred2["factors"]["context"]["home_advantage_gamma"] < 50:
    errors.append(f"Host advantage too low: {pred2['factors']['context']['home_advantage_gamma']}")

# Check Argentina vs Jordan is heavily favored
if pred4["wdl"]["home_win"] < 0.50:
    errors.append(f"Argentina vs Jordan home_win too low: {pred4['wdl']['home_win']}")

# Check expected goals are reasonable
for p in [pred, pred2, pred3, pred4]:
    lam = p["expected_goals"]["home"]
    mu = p["expected_goals"]["away"]
    if not (0.2 <= lam <= 3.5):
        errors.append(f"Expected home goals out of range: {lam}")
    if not (0.1 <= mu <= 3.0):
        errors.append(f"Expected away goals out of range: {mu}")

if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
else:
    print("ALL VALIDATIONS PASSED")
