# Quick debug: simulate what uvicorn does
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
os.chdir(os.path.join(os.getcwd(), 'backend'))

from pathlib import Path
import api.models as m
print("__file__:", m.__file__)
model_dir = Path(m.__file__).resolve().parent.parent / "models"
print("model_dir:", model_dir)
print("exists:", model_dir.exists())
if model_dir.exists():
    stacking = list(model_dir.glob("stacking_*.json"))
    print("stacking files:", len(stacking))
    for s in stacking[:3]:
        print("  ", s.name)

# Now call the actual function
result = m.list_ensemble_leagues()
print("Result count:", result["count"])
