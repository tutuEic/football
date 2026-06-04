"""Test wc_simulator.py — quick verification."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from engine.wc_simulator import (
    load_groups, simulate_tournament,
    format_simulation_report,
)

print("=" * 70)
print("TEST: Tournament Simulation (50 iterations)")
print("=" * 70)

start = time.time()
result = simulate_tournament(n_sims=50)
elapsed = time.time() - start

print(f"  Duration: {elapsed:.1f}s")
print(format_simulation_report(result))

# Validation
print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)
errors = []
champ_total = sum(result["champion_probs"].values())
if abs(champ_total - 1.0) > 0.05:
    errors.append(f"Champion probs sum = {champ_total:.3f}, expected ~1.0")
if len(result["group_advance"]) < 24:
    errors.append(f"Too few advancing teams: {len(result['group_advance'])}")
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
else:
    print("ALL VALIDATIONS PASSED")
