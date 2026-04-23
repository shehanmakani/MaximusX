from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import httpx


DEFAULT_EMULATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "future-self-emulator"
    / "backend"
    / "app"
    / "services"
    / "engine.py"
)


class FutureSelfBridge:
    def __init__(self, api_url: str | None = None, engine_path: str | None = None):
        self.api_url = api_url or os.getenv("FUTURE_SELF_API_URL")
        self.engine_path = Path(engine_path or os.getenv("FUTURE_SELF_ENGINE_PATH", DEFAULT_EMULATOR_PATH))

    def recommend_next_action(self, profile: str, context: dict[str, Any]) -> dict[str, Any]:
        if self.api_url:
            try:
                response = httpx.post(
                    f"{self.api_url.rstrip('/')}/next-action",
                    json={"profile": profile, "context": context},
                    timeout=15,
                )
                response.raise_for_status()
                return response.json()
            except Exception:
                pass

        module = self._load_engine_module()
        return module.recommend_next_action(profile, context)

    def _load_engine_module(self):
        spec = importlib.util.spec_from_file_location("future_self_engine", self.engine_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load future-self emulator engine from {self.engine_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
