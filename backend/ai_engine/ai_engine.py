# backend/ai_engine/ai_engine.py

"""
Main AI Engine — Translates natural language beliefs into trading strategies.
Integrates belief parsing, goal evaluation, asset class selection, and GPT-4-powered strategy logic.
Now includes mismatch detection for ML misfires.
"""

import os
import json
import math
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from backend.belief_parser import parse_belief
from backend.market_data import get_latest_price, get_weekly_high_low, get_option_expirations
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief as evaluate_goal
from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
from backend.logger.strategy_logger import log_strategy

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")
client = OpenAI(api_key=OPENAI_API_KEY)

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

def run_ai_engine(belief: str, risk_profile: str = "moderate", user_id: str = "anonymous") -> dict:
    parsed = parse_belief(belief)
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
        print(f"[ERROR] get_latest_price failed for {ticker}: {e}")
        latest = -1.0

    try:
        high_low = get_weekly_high_low(ticker)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low failed for {ticker}: {e}")
        high_low = (-1.0, -1.0)

    price_info = {"latest": clean_float(latest)}
    high_low = (clean_float(high_low[0]), clean_float(high_low[1]))

    print("\n🔍 [AI ENGINE DEBUG INFO]")
    print(f"Belief: {belief}")
    print(f"→ Ticker: {ticker}, Direction: {direction}, Tags: {tags}")
    print(f"→ Confidence: {confidence}, Risk Profile: {risk_profile}")
    print(f"→ Goal: {goal_type}, Multiplier: {multiplier}, Timeframe: {timeframe}")
    print(f"→ Asset Class: {asset_class}, Expiry Date: {expiry_date}")
    print(f"→ Latest Price: {latest}, Weekly High/Low: {high_low}")

    bond_tags = ["bond", "ladder", "income", "fixed income"]
    is_bond_ladder = (
        "bond ladder" in belief.lower()
        or any(tag in tags for tag in bond_tags)
        or asset_class == "bond"
    )

    strategy_prompt = f"""
You are a financial strategist. Based on the user's belief: "{belief}", generate a trading strategy.

Include:
- type (e.g., long call, bull put spread, buy equity, buy bond ETF)
- trade_legs (e.g., 'buy 1 call 150 strike', 'sell 1 put 140 strike')
- expiration (in 'YYYY-MM-DD' format or 'N/A')
- target_return (expected gain %)
- max_loss (worst-case loss %)
- time_to_target (e.g., 2 weeks, 3 months)
- explanation (why this fits belief)

Context:
- Ticker: {ticker}
- Direction: {direction}
- Asset Class: {asset_class}
- Latest Price: {latest}
- Goal: {goal_type}, Multiplier: {multiplier}, Timeframe: {timeframe}
- Confidence: {confidence}, Risk Profile: {risk_profile}
"""

    if is_bond_ladder:
        strategy_prompt += """
NOTE: The user appears interested in a bond ladder or income strategy.
Recommend a bond ETF ladder using AGG (broad), IEF (mid-term), and SHY (short-term).
Explain the maturity staggering, income generation, and diversification benefits clearly.
"""

    strategy_prompt += "\nRespond ONLY with valid JSON. Do not include explanations, markdown, or formatting."

    print("🧠 Using GPT-4 to generate strategy...\n")

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": strategy_prompt}],
            temperature=0.7,
        )
        gpt_output = response.choices[0].message.content.strip()
        print("🧾 GPT RAW OUTPUT:\n", gpt_output)

        if gpt_output.startswith("{"):
            strategy = json.loads(gpt_output)
            if isinstance(strategy, dict) and "strategy" in strategy:
                strategy = strategy["strategy"]
        else:
            raise ValueError("GPT returned non-JSON response.")

    except Exception as e:
        print(f"[ERROR] GPT-4 strategy generation failed: {e}")
        strategy = {
            "type": "error",
            "trade_legs": [],
            "expiration": "N/A",
            "target_return": 0,
            "max_loss": 0,
            "time_to_target": "N/A",
            "explanation": f"Failed to generate strategy: {e}"
        }

    # ✅ EXPIRATION OVERRIDE LOGIC
    if asset_class == "options":
        raw_expiry = strategy.get("expiration")
        if is_expired(raw_expiry):
            fallback_dates = get_option_expirations(ticker)
            if fallback_dates:
                strategy["expiration"] = fallback_dates[0]  # use soonest valid
                print(f"[FIXED] Overriding bad expiration with fallback: {strategy['expiration']}")

    # ✅ Detect directional mismatch for feedback learning
    generated_type = strategy.get("type", "").lower()
    if goal_type == "multiply" and direction in ["bullish", "bearish"]:
        if "straddle" in generated_type or "neutral" in generated_type:
            print("⚠️ [MISMATCH] Strategy may not match directional intent. Flagging for retraining.")

    explanation = strategy.get("explanation", "Strategy explanation not available.")
    log_strategy(belief, explanation, user_id, strategy)

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
    }
