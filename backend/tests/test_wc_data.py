"""Test wc_data.py — verify all 48 WC teams produce valid squad analysis."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.wc_data import analyze_squad, analyze_all_wc_teams

# Test 1: Single team analysis (France)
print("=" * 70)
print("TEST 1: Single team — France")
print("=" * 70)
fr = analyze_squad("France")
print(f"  Squad size:      {fr['squad_size']}")
print(f"  Starting XI:     {fr['starting_xi']}")
print(f"  Attack quality:  {fr['attack_quality']}")
print(f"  Defense quality: {fr['defense_quality']}")
print(f"  Squad depth:     {fr['squad_depth']}")
print(f"  Avg age:         {fr['avg_age']}")
print(f"  Age score:       {fr['age_score']}")
print(f"  League quality:  {fr['league_quality']}")
print(f"  Cohesion:        {fr['cohesion']}")
print(f"  Set piece:       {fr['set_piece_strength']}")
print(f"  Elo bonus:       {fr['elo_bonus']}")
print(f"  Elo breakdown:   {fr['elo_breakdown']}")
print(f"  Top players:     {fr['top_players']}")

# Test 2: All 48 teams
print("\n" + "=" * 70)
print("TEST 2: All 48 WC teams")
print("=" * 70)

results = analyze_all_wc_teams()

# Sort by elo_bonus descending
ranked = sorted(results.items(), key=lambda x: x[1]["elo_bonus"], reverse=True)

print(f"\n{'Team':25s} {'Sqd':>4s} {'XI':>5s} {'ATK':>5s} {'DEF':>5s} {'DPT':>5s} "
      f"{'Age':>5s} {'Lge':>5s} {'Coh':>5s} {'SP':>5s} {'ELO':>6s}")
print("-" * 95)
for team, data in ranked:
    print(f"{team:25s} {data['squad_size']:>4d} "
          f"{data['starting_xi']:>5.1f} {data['attack_quality']:>5.1f} "
          f"{data['defense_quality']:>5.1f} {data['squad_depth']:>5.1f} "
          f"{data['avg_age']:>5.1f} {data['league_quality']:>5.1f} "
          f"{data['cohesion']:>5.3f} {data['set_piece_strength']:>5.3f} "
          f"{data['elo_bonus']:>+6.1f}")

# Validation checks
print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)

errors = []
for team, data in ranked:
    if data["squad_size"] == 0:
        errors.append(f"{team}: no players found")
    if not (0 <= data["starting_xi"] <= 99):
        errors.append(f"{team}: starting_xi={data['starting_xi']} out of range")
    if not (0 <= data["age_score"] <= 1):
        errors.append(f"{team}: age_score={data['age_score']} out of range")
    if not (0 <= data["cohesion"] <= 1):
        errors.append(f"{team}: cohesion={data['cohesion']} out of range")
    if not (0 <= data["set_piece_strength"] <= 1):
        errors.append(f"{team}: set_piece={data['set_piece_strength']} out of range")

if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
else:
    print("ALL VALIDATIONS PASSED")

# Sanity checks
print("\nSanity checks:")
print(f"  France attack_quality > Brazil attack_quality: "
      f"{results['France']['attack_quality']:.1f} > {results['Brazil']['attack_quality']:.1f} = "
      f"{results['France']['attack_quality'] > results['Brazil']['attack_quality']}")
print(f"  Germany cohesion > Senegal cohesion: "
      f"{results['Germany']['cohesion']:.3f} > {results['Senegal']['cohesion']:.3f} = "
      f"{results['Germany']['cohesion'] > results['Senegal']['cohesion']}")
print(f"  England league_quality > Morocco league_quality: "
      f"{results['England']['league_quality']:.1f} > {results['Morocco']['league_quality']:.1f} = "
      f"{results['England']['league_quality'] > results['Morocco']['league_quality']}")
