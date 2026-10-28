"""
One place that decides which belief engine runs.

ENGINE_VERSION=v4 (default): Claude-powered v4 engine (backend/v4).
ENGINE_VERSION=legacy:       the original GPT-4 + ML engine (needs OPENAI_API_KEY).

The legacy engine is imported only when it is actually used, so the app starts
fast and does not need an OpenAI key unless legacy is switched on.
"""
from __future__ import annotations

import os


def engine_version() -> str:
    return "legacy" if os.getenv("ENGINE_VERSION", "v4").lower() == "legacy" else "v4"


def run_belief(belief: str, user_id: str = "anonymous", risk_profile: str = "moderate", source: str = "user") -> dict:
    """Return a strategy for a belief from whichever engine is active."""
    if engine_version() == "legacy":
        from backend.ai_engine.ai_engine import run_ai_engine

        return run_ai_engine(belief, risk_profile=risk_profile, user_id=user_id)
    from backend.v4 import engine

    return engine.process_belief(belief, user_id or "anonymous", risk_profile or "moderate", source=source)


def generate_basket(goal: str, user_id: str = "anonymous") -> dict:
    """Asset basket for a plain-language investing goal."""
    if engine_version() == "legacy":
        from backend.ai_engine.ai_engine import generate_asset_basket

        return generate_asset_basket(goal, user_id=user_id)
    from backend.v4 import basket

    return basket.generate(goal, user_id=user_id)
