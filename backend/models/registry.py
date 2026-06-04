# -*- coding: utf-8 -*-
"""
Model Registry — version management, loading, and A/B testing.
"""
import json, os, time
from pathlib import Path
from datetime import datetime

MODEL_DIR = Path(__file__).resolve().parent.parent / 'models'
REGISTRY_FILE = MODEL_DIR / 'registry.json'


class ModelRegistry:
    """Manages model versions, metadata, and loading."""

    def __init__(self, model_dir=None):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self):
        if REGISTRY_FILE.exists():
            return json.loads(REGISTRY_FILE.read_text(encoding='utf-8'))
        return {"models": {}, "active": {}}

    def _save_registry(self):
        REGISTRY_FILE.write_text(
            json.dumps(self.registry, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def register_model(self, model_type: str, league: str, path: str,
                       metrics: dict, metadata: dict = None):
        """Register a trained model."""
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"{model_type}_{league}"

        if key not in self.registry["models"]:
            self.registry["models"][key] = []

        entry = {
            "version": version,
            "path": str(path),
            "metrics": metrics,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
            "status": "registered",
        }
        self.registry["models"][key].append(entry)
        self._save_registry()
        print(f"Registered model: {key} v{version}")
        return version

    def activate_model(self, model_type: str, league: str, version: str = None):
        """Activate a specific model version (or latest)."""
        key = f"{model_type}_{league}"
        models = self.registry["models"].get(key, [])

        if not models:
            print(f"No models found for {key}")
            return None

        if version:
            target = [m for m in models if m["version"] == version]
        else:
            target = [models[-1]]  # Latest

        if target:
            self.registry["active"][key] = target[0]
            self._save_registry()
            print(f"Activated: {key} v{target[0]['version']}")
            return target[0]

        return None

    def get_active_model(self, model_type: str, league: str) -> dict:
        """Get the active model for a given type and league."""
        key = f"{model_type}_{league}"
        return self.registry["active"].get(key)

    def list_models(self, model_type: str = None, league: str = None):
        """List all registered models."""
        results = []
        for key, versions in self.registry["models"].items():
            if model_type and not key.startswith(model_type):
                continue
            if league and not key.endswith(league):
                continue
            for v in versions:
                results.append({"key": key, **v})
        return results

    def compare_models(self, model_type: str, league: str):
        """Compare all versions of a model."""
        key = f"{model_type}_{league}"
        models = self.registry["models"].get(key, [])
        if not models:
            return None

        comparison = []
        for m in models:
            comparison.append({
                "version": m["version"],
                "metrics": m["metrics"],
                "status": m["status"],
            })
        return comparison
