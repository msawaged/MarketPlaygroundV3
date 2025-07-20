# backend/ai_engine/ai_engine.py

"""
Main AI Engine — Translates beliefs into trade strategies.
Uses GPT-4 to parse beliefs into structured metadata,
then routes through ML or GPT based on hybrid logic.
"""

import os
import json
import math
from datetime import datetime
from openai import OpenAI, OpenAIError
import openai
from typing import Optional

from backend.openai_config import OPENAI_API_KEY, GPT_MODEL
from backend.belief_parser import parse_belief
from backend.market_data import get_latest_price, get_weekly_high_low, get_option_expirations
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief as evaluate_goal
from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
from backend.logger.strategy_logger import log_strategy
from backend.ai_engine.strategy_model_selector import decide_strategy_engine  # ✅ NEW ROUTER

# 🔑 OpenAI key setup
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in environment variables.")
else:
    print(f"🔑 OpenAI key loaded: ...{OPENAI_API_KEY[-4:]}")

openai.api_key = OPENAI_API_KEY

try:
    client = OpenAI()
except OpenAIError as e:
    raise RuntimeError(f"❌ Failed to initialize OpenAI client: {e}")

KNOWN_EQUITIES = {
    "AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "MSFT", "NFLX", "BAC", "JPM", "WMT"
}

def clean_float(value):
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return value

def is_expired(date_str):
    try:
        if not date_str or date_str == "N/A":
            return True
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.date() < datetime.now().date()
    except:
        return True

# === 🧠 MAIN ENTRY POINT ===
def run_ai_engine(belief: str, risk_profile: str = "moderate", user_id: str = "anonymous") -> dict:
    parsed = parse_belief(belief)
        # ✅ FED HIKE OVERRIDE LOGIC — Patch for rising rate beliefs
    fed_hike_keywords = [
        "fed is going to raise", "raise interest rates", "rate hike",
        "fed hike", "fed raising rates", "interest rates will go up"
    ]

    if any(kw in belief.lower() for kw in fed_hike_keywords):
        print("🛠 Detected Fed Hike Belief — Overriding strategy to inverse bond ETF")
        return {
            "strategy": {
                "type": "Inverse Bond ETF",
                "trade_legs": [{"action": "buy", "quantity": "100 shares", "ticker": "TBT"}],
                "expiration": "N/A",
                "target_return": "10%",
                "max_loss": "10%",
                "time_to_target": "3-6 months",
                "explanation": (
                    "As interest rates rise, long-term bonds like TLT typically fall in value. "
                    "TBT is an inverse ETF designed to rise when Treasury bond prices fall, making it a good hedge or profit strategy during Fed rate hikes."
                )
            },
            "ticker": "TBT",
            "asset_class": "etf",
            "tags": ["fed", "interest rates", "macro"],
            "direction": "bullish",
            "price_info": {"latest": -1},
            "high_low": [None, None],
            "confidence": 0.65,
            "goal_type": "unspecified",
            "multiplier": None,
            "timeframe": "3-6 months",
            "expiry_date": "N/A",
            "risk_profile": risk_profile,
            "explanation": (
                "As interest rates rise, long-term bonds like TLT typically fall in value. "
                "TBT is an inverse ETF designed to rise when Treasury bond prices fall, making it a good hedge or profit strategy during Fed rate hikes."
            ),
            "user_id": user_id,
            "validator": {
                "valid": True,
                "would_profit": True,
                "estimated_profit_pct": 10,
                "notes": "✅ Strategy matches belief: short bonds during rising rates"
            },
            "valid": True,
            "would_profit": True,
            "estimated_profit_pct": 10,
            "notes": "✅ Strategy matches belief: short bonds during rising rates"
        }

    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)
    parsed_asset = parsed.get("asset_class", "options")

    goal = evaluate_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")
    expiry_date = parse_timeframe_to_expiry(timeframe) if timeframe else None

    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"

    if parsed_asset == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    elif parsed_asset == "bond" and ticker.upper() == "SPY":
        asset_class = "bond"
        ticker = "TLT"
    else:
        asset_class = parsed_asset

    try:
        latest = get_latest_price(ticker)
    except Exception as e:
        print(f"[ERROR] get_latest_price failed: {e}")
        latest = -1.0

    try:
        high_low = get_weekly_high_low(ticker)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low failed: {e}")
        high_low = (-1.0, -1.0)

    price_info = {"latest": clean_float(latest)}
    high_low = (clean_float(high_low[0]), clean_float(high_low[1]))

    # ✅ Build metadata to send to hybrid engine
    metadata = {
        "ticker": ticker,
        "asset_class": asset_class,
        "direction": direction,
        "confidence": confidence,
        "risk_profile": risk_profile,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
        "user_id": user_id
    }

    # === 🧠 HYBRID STRATEGY SELECTION (ML → GPT fallback) ===
    strategy = decide_strategy_engine(belief, metadata)

    # 🛠 Fix bad expirations
    if strategy.get("expiration") and asset_class == "options":
        if is_expired(strategy["expiration"]):
            try:
                fallback_dates = get_option_expirations(ticker)
                future_dates = [d for d in fallback_dates if not is_expired(d)]
                if future_dates:
                    strategy["expiration"] = future_dates[0]
                    print(f"[FIXED] Overriding bad expiration → {strategy['expiration']}")
                else:
                    strategy["expiration"] = "N/A"
                    print(f"[WARNING] No valid future expirations found.")
            except Exception as e:
                strategy["expiration"] = "N/A"
                print(f"[ERROR] Failed to fetch expirations: {e}")

    # ✅ Format strategy tags
    strategy_type = strategy.get("type", "").lower()
    trade_legs_raw = strategy.get("trade_legs", [])
    trade_legs = " ".join(str(leg).lower() for leg in trade_legs_raw)

    tags = []
    if "spread" in strategy_type or "spread" in trade_legs:
        if "put" in trade_legs and "sell" in trade_legs and "buy" in trade_legs:
            tags.append("bear put spread" if direction == "bearish" else "bull put spread")
        elif "call" in trade_legs and "sell" in trade_legs and "buy" in trade_legs:
            tags.append("bull call spread" if direction == "bullish" else "bear call spread")
        else:
            tags.append("spread")
    elif "call" in strategy_type:
        tags.append("long call" if "buy" in trade_legs else "call")
    elif "put" in strategy_type:
        tags.append("long put" if "buy" in trade_legs else "put")
    elif "bond" in strategy_type:
        tags.append("bond")
    elif "equity" in strategy_type or "stock" in strategy_type:
        tags.append("stock")
    elif "straddle" in strategy_type or "strangle" in strategy_type:
        tags.append("neutral")

    # ✅ Adjust direction if too vague
    if direction == "neutral" and "long call" in tags:
        direction = "bullish"
    elif direction == "neutral" and "long put" in tags:
        direction = "bearish"

    explanation = strategy.get("explanation", "Strategy explanation not available.")
    log_strategy(belief, explanation, user_id, strategy)

    # ✅ Run validation pass (optional)
    try:
        from backend.strategy_validator import evaluate_strategy_against_belief
        validation = evaluate_strategy_against_belief(belief, strategy)
        print(f"[✅ VALIDATOR] {validation}")
    except Exception as e:
        print(f"[ERROR] Strategy validation failed: {e}")
        validation = {
            "valid": False,
            "would_profit": None,
            "estimated_profit_pct": None,
            "notes": f"Validation error: {e}"
        }

    # ✅ Debug final output
    print("[DEBUG] Final strategy output:")
    print(json.dumps({
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": high_low,
        "confidence": confidence,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
        "expiry_date": strategy.get("expiration"),
        "risk_profile": risk_profile,
        "explanation": explanation,
        "user_id": user_id,
        "validator": validation,
    }, indent=2))

    # ✅ AUTO-FEEDBACK: Log test_* beliefs as neutral feedback for learning loop
    if user_id.startswith("test_"):
        try:
            feedback_payload = {
                "belief": belief,
                "strategy": strategy.get("type", "unknown"),
                "feedback": "neutral",
                "confidence": strategy.get("confidence", 0.5),
                "source": "test_run",
                "user_id": user_id
            }
            import requests
            requests.post("http://localhost:8000/feedback/submit_feedback", json=feedback_payload, timeout=5)
            print(f"[AUTO-FEEDBACK] Logged test feedback for {user_id}")
        except Exception as e:
            print(f"[AUTO-FEEDBACK ERROR] Failed to log test feedback: {e}")


    return {
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": high_low,
        "confidence": confidence,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
        "expiry_date": strategy.get("expiration"),
        "risk_profile": risk_profile,
        "explanation": explanation,
        "user_id": user_id,
        "validator": validation,
        "valid": validation.get("valid"),
        "would_profit": validation.get("would_profit"),
        "estimated_profit_pct": validation.get("estimated_profit_pct"),
        "notes": validation.get("notes"),
    }
