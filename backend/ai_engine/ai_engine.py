"""
Main AI Engine — Translates natural language beliefs into trading strategies.
Integrates belief parsing, goal evaluation, asset class selection, and GPT-4-powered strategy logic.
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from backend.belief_parser import parse_belief
from backend.market_data import get_latest_price, get_weekly_high_low
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief as evaluate_goal
from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
from backend.logger.strategy_logger import log_strategy

# Load environment variables from .env file at runtime
load_dotenv()

# Securely read OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Initialize OpenAI client with API key
client = OpenAI(api_key=OPENAI_API_KEY)

# Known equities override ETF misclassification
KNOWN_EQUITIES = {
    "AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "MSFT", "NFLX", "BAC", "JPM", "WMT"
}

def run_ai_engine(belief: str, risk_profile: str = "moderate", user_id: str = "anonymous") -> dict:
    """
    Core AI pipeline: 
    - Parse the user belief to extract key info (direction, ticker, tags, confidence, asset class)
    - Parse user financial goal from belief (goal type, multiplier, timeframe)
    - Use fallback logic for missing ticker or asset class
    - Fetch latest market price and weekly high/low for ticker
    - Compose a detailed GPT-4 prompt with all context
    - Call GPT-4 chat completions API to generate a JSON trading strategy
    - Handle API errors gracefully by returning error info in the strategy
    - Log the generated strategy with associated belief and user info
    - Return a flat dictionary with all info for frontend consumption
    """

    # Step 1: Parse belief for key info
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)
    parsed_asset = parsed.get("asset_class", "options")

    # Step 2: Parse financial goal from belief
    goal = evaluate_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")
    expiry_date = parse_timeframe_to_expiry(timeframe) if timeframe else None

    # Step 3: Fallback ticker if missing
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"

    # Step 4: Fix asset class misclassification
    if parsed_asset == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    elif parsed_asset == "bond" and ticker.upper() == "SPY":
        asset_class = "bond"
        ticker = "TLT"
    else:
        asset_class = parsed_asset

    # Step 5: Fetch market data, handle errors safely
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

    price_info = {"latest": latest}

    # Debug output for traceability
    print("\n🔍 [AI ENGINE DEBUG INFO]")
    print(f"Belief: {belief}")
    print(f"→ Ticker: {ticker}, Direction: {direction}, Tags: {tags}")
    print(f"→ Confidence: {confidence}, Risk Profile: {risk_profile}")
    print(f"→ Goal: {goal_type}, Multiplier: {multiplier}, Timeframe: {timeframe}")
    print(f"→ Asset Class: {asset_class}, Expiry Date: {expiry_date}")
    print(f"→ Latest Price: {latest}, Weekly High/Low: {high_low}")
    print("🧠 Using GPT-4 to generate strategy...\n")

    # Step 6: Build prompt for GPT-4
    strategy_prompt = f"""
You are a financial strategist. Based on the user's belief: "{belief}", generate a trading strategy.

Include:
- type (e.g., long call, bull put spread, buy equity, buy bond ETF)
- trade_legs (e.g., 'buy 1 call 150 strike', 'sell 1 put 140 strike')
- expiration (in 'YYYY-MM-DD' format or 'N/A' if not applicable)
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

Output valid JSON only.
"""

    # Step 7: Call GPT-4 API and parse JSON response
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": strategy_prompt}],
            temperature=0.7,
        )
        gpt_output = response.choices[0].message.content.strip()
        strategy = json.loads(gpt_output)

        # Unwrap nested strategy if necessary
        if isinstance(strategy, dict) and "strategy" in strategy and isinstance(strategy["strategy"], dict):
            strategy = strategy["strategy"]

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

    # Step 8: Prepare explanation field
    explanation = strategy.get("explanation", "Strategy explanation not available.")

    # Step 9: Log strategy for analytics and tracking
    log_strategy(belief, explanation, user_id, strategy)

    # Step 10: Return a flat dictionary with all relevant info
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
        "expiry_date": expiry_date,
        "risk_profile": risk_profile,
        "explanation": explanation,
        "user_id": user_id,
    }
