"""
Asset basket builder (v4, Claude).

Turns a plain-language goal ("70% stocks, 30% bonds for moderate growth",
"something safe for a house down payment in 3 years") into 2-6 ETFs/stocks
with allocations that add up to 100%. Tickers are checked against Alpaca when
market data is available. Same response shape the existing Basket Builder page reads.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from . import interpreter, market

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["basket", "goal", "risk_profile", "historical_note"],
    "properties": {
        "basket": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ticker", "type", "allocation_pct", "rationale"],
                "properties": {
                    "ticker": {"type": "string"},
                    "type": {"type": "string", "enum": ["stock", "etf", "bond etf", "commodity etf", "cash-like"]},
                    "allocation_pct": {"type": "number"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "goal": {"type": "string"},
        "risk_profile": {"type": "string", "enum": ["conservative", "moderate", "aggressive"]},
        "historical_note": {"type": "string"},
    },
}

SYSTEM = """You build simple, diversified investment baskets for MarketPlayground users from a plain-language goal.

Rules:
- 2 to 6 holdings, US-listed and liquid; prefer broad, low-cost ETFs, and individual stocks only when the goal names them.
- Allocations are whole-number percentages that add up to 100. Respect any split the user states (e.g. 70/30).
- type: stock, etf, bond etf, commodity etf, or cash-like (e.g. short-term Treasury ETFs).
- rationale: one short sentence per holding, in plain words.
- goal: restate the goal in under 12 words.
- risk_profile: from the user's wording and time horizon.
- historical_note: one sentence on how a mix like this has tended to behave (e.g. ups and downs, typical drawdowns). No promised or predicted returns.
- No crypto unless the user asks for it."""


def _fallback(goal: str) -> dict:
    return {
        "basket": [
            {"ticker": "VTI", "type": "etf", "allocation": "60%", "rationale": "Broad US stock market exposure."},
            {"ticker": "BND", "type": "bond etf", "allocation": "40%", "rationale": "Diversified US investment-grade bonds."},
        ],
        "goal": goal or "Balanced growth",
        "estimated_return": "Varies with markets; not guaranteed.",
        "risk_profile": "moderate",
        "engine": "fallback",
    }


def generate(goal: str, user_id: Optional[str] = None, client: Any = None) -> dict:
    goal = (goal or "").strip()[:500]
    if not goal:
        return _fallback("")
    client = client or interpreter._client()
    resp = client.messages.create(
        model=os.getenv("MP_BASKET_MODEL", interpreter.DEFAULT_MODEL),
        max_tokens=1500,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Goal: {goal}"}],
        extra_body={"output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}},
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    data = json.loads(text)

    items = []
    for it in data.get("basket", [])[:6]:
        t = (it.get("ticker") or "").upper().strip()
        if not t:
            continue
        try:
            if market.asset_info(t) is None:
                continue  # not a tradable US listing
        except market.MarketDataError:
            pass  # market data unavailable: keep Claude's pick rather than fail
        items.append({**it, "ticker": t, "allocation_pct": max(0.0, float(it.get("allocation_pct") or 0))})
    if not items:
        return _fallback(goal)

    # normalize to whole percents summing to 100
    total = sum(i["allocation_pct"] for i in items) or 1.0
    pcts = [round(i["allocation_pct"] * 100 / total) for i in items]
    pcts[pcts.index(max(pcts))] += 100 - sum(pcts)
    basket = [{"ticker": i["ticker"], "type": i["type"], "allocation": f"{p}%", "rationale": i["rationale"]}
              for i, p in zip(items, pcts) if p > 0]
    return {
        "basket": basket,
        "goal": data.get("goal") or goal,
        "estimated_return": f"{data.get('historical_note', '').strip()} Past behavior does not guarantee future results.".strip(),
        "risk_profile": data.get("risk_profile", "moderate"),
        "engine": "v4",
    }
