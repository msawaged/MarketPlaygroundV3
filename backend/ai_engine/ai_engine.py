# backend/ai_engine/ai_engine.py
print("🧪 ai_engine.py: Top of file loaded.")

"""
Main AI Engine — Translates beliefs into trade strategies.
Includes GPT-4 integration, goal parsing, bond logic, robust fallback handling.
MINIMAL FIXES APPLIED by Claude
"""
import time
import os
import json
import math
from datetime import datetime
from openai import OpenAI, OpenAIError
import openai
from backend.ai_engine.strategy_explainer import generate_strategy_explainer

print("🔍 ai_engine.py: All imports finished.")


from typing import Optional
from backend.openai_config import OPENAI_API_KEY, GPT_MODEL
print("✅ Imported openai_config")

from backend.belief_parser import parse_belief
print("✅ Imported belief_parser")

from backend.market_data import (
    get_latest_price,
    get_weekly_high_low,
    get_option_expirations,
)
print("✅ Imported market_data")

from backend.ai_engine.goal_evaluator import (
    evaluate_goal_from_belief as evaluate_goal,
)
print("✅ Imported goal_evaluator")

from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
print("✅ Imported expiry_utils")

from backend.logger.strategy_logger import log_strategy
print("✅ Imported strategy_logger")

from backend.ai_engine.strategy_model_selector import decide_strategy_engine
print("✅ Imported strategy_model_selector")



if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in environment variables.")
else:
    print(f"🔑 OpenAI key loaded: ...{OPENAI_API_KEY[-4:]}")

    openai.api_key = OPENAI_API_KEY

    client = None  # Will be initialized lazily later
    print("🧪 [Debug] OpenAI client set to None (lazy init ready)")

    KNOWN_EQUITIES = {
        "AAPL",
        "TSLA",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "MSFT",
        "NFLX",
        "BAC",
        "JPM",
        "WMT",
    }


 # === 🔁 Lazy Load Helper: Create OpenAI client only when needed ===
client = None
print("✅ [Debug] OpenAI client set to None (lazy init ready)")

def get_openai_client():
    """
    Lazily initializes the OpenAI client only when called.
    Prevents backend hangs or timeouts on startup.
    """
    global client
    if client is None:
        try:
            client = OpenAI()  # ✅ not get_openai_client()
        except OpenAIError as e:
            raise RuntimeError(f"❌ Failed to initialize OpenAI Client: {e}")
    return client



# === 🧠 Helper: Parse GPT output into structured strategy ===
def parse_gpt_output_to_strategy(output: str) -> Optional[dict]:
    """
    Attempts to parse GPT-4 output (string) into a structured strategy dictionary.

    Returns None if parsing fails or required keys are missing.
    """
    try:
        strategy = json.loads(output)
        required_keys = {
            "type",
            "trade_legs",
            "expiration",
            "target_return",
            "max_loss",
            "time_to_target",
            "explanation",
        }
        if all(key in strategy for key in required_keys):
            return strategy
    except Exception as e:
        print(f"[GPT PARSE ERROR] Failed to parse GPT output: {e}")
    return None

def attempt_gpt_strategy_parse(belief, gpt_raw_output, context) -> Optional[dict]:
    """
    🧠 Soft fallback GPT strategy parser — uses keyword-based recovery from natural language output.
    Tries to infer structure when json.loads() fails or GPT output is unstructured.
    """
    gpt_lower = gpt_raw_output.lower()
    strategy = {}

    if "call option" in gpt_lower:
        strategy = {
            "type": "Call Option",
            "trade_legs": ["buy 1 call slightly OTM"],
            "expiration": "N/A",
            "target_return": "15%",
            "max_loss": "Premium Paid",
            "time_to_target": "1 month",
            "explanation": gpt_raw_output.strip(),
        }

    elif "bull call spread" in gpt_lower:
        strategy = {
            "type": "Bull Call Spread",
            "trade_legs": ["buy 1 call", "sell 1 higher call"],
            "expiration": "N/A",
            "target_return": "20%",
            "max_loss": "Net Debit",
            "time_to_target": "1 month",
            "explanation": gpt_raw_output.strip(),
        }

    elif "equity" in gpt_lower or "buy stock" in gpt_lower:
        strategy = {
            "type": "Buy Equity",
            "trade_legs": [f"buy 100 shares of {context.get('ticker', 'XYZ')}"],
            "expiration": "N/A",
            "target_return": "10%",
            "max_loss": "10%",
            "time_to_target": "3 months",
            "explanation": gpt_raw_output.strip(),
        }

    if strategy:
        print("✅ [Soft Parser] Recovered strategy from GPT prose.")
        strategy["source"] = "gpt_soft_parse"
        return strategy

    print("[❌ Soft Parser] Failed to extract strategy from prose.")
    return None


def clean_float(value):
    if value is None or (
        isinstance(value, float) and (math.isnan(value) or math.isinf(value))
    ):
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

def fix_expiration(ticker: str, raw_expiry: str) -> str:
    """
    Validates and corrects expiration. If invalid, replaces with the next valid expiration.
    Returns "N/A" if no valid future expirations exist.
    """
    try:
        if is_expired(raw_expiry):
            fallback_dates = get_option_expirations(ticker)
            future_dates = [d for d in fallback_dates if not is_expired(d)]
            if future_dates:
                print(f"[FIXED] Overriding bad expiration → {future_dates[0]}")
                return future_dates[0]
            else:
                print("[WARNING] No valid expirations found. Using 'N/A'.")
                return "N/A"
        return raw_expiry
    except Exception as e:
        print(f"[ERROR] Expiration fix failed: {e}")
        return "N/A"



def run_ai_engine(
    belief: str, risk_profile: str = "moderate", user_id: str = "anonymous"
) -> dict:
    start_time = time.time()  # ADD THIS LINE HERE
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

    # 🧠 Fallback logic if no ticker was detected from belief
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"  # Safe fallback

    # ✅ Properly assign asset class after ticker is finalized
    if parsed_asset == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    elif parsed_asset == "bond" and ticker.upper() == "SPY":
        asset_class = "bond"
        ticker = "TLT"  # Safer fallback for bond beliefs
    else:
        asset_class = parsed_asset

    # ✅ Get price data safely
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

    # ✅ Normalize price data
    price_info = {
        "latest": clean_float(latest),
        "high": clean_float(high_low[0]),
        "low": clean_float(high_low[1]),
    }

    # ✅ Detect if this is a bond ladder-style belief
    bond_tags = ["bond", "ladder", "income", "fixed income"]
    is_bond_ladder = (
        "bond ladder" in belief.lower()
        or any(tag in tags for tag in bond_tags)
        or asset_class == "bond"
    )

    # ✅ Construct the base prompt for GPT strategy generation
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

    # === ✅ NEW: Route strategy generation through hybrid GPT/ML selector ===
    strategy = decide_strategy_engine(
        belief,
        {
            "direction": direction,
            "ticker": ticker,
            "tags": tags,
            "asset_class": asset_class,
            "goal_type": goal_type,
            "multiplier": multiplier,
            "timeframe": timeframe,
            "risk_profile": risk_profile,
            "confidence": confidence,
            "price_info": price_info,
        },
    )
    
    # 🚫 CRITICAL PRODUCTION FIX: Check if sentiment validation blocked the strategy
    if strategy is None:
        print("🚫 STRATEGY BLOCKED: Sentiment validation prevented misaligned strategy")
        return {
            "error": "Strategy blocked due to sentiment misalignment",
            "strategy": None,
            "ticker": ticker,
            "direction": direction,
            "user_id": user_id,
            "processing_time": time.time() - start_time,
            "reason": "Bullish belief cannot generate neutral/bearish strategies in production mode"
        }

    # === 🔁 Soft Fallback Parser Injection for GPT-4 ===
    try:
        from backend.ai_engine.gpt4_strategy_generator import generate_strategy_with_validation
        
        # Get sentiment from belief parser for validation
        detected_sentiment = direction  # Use the direction already parsed above
        gpt_raw_output = generate_strategy_with_validation(belief, detected_sentiment)

        try:
            gpt_strategy = json.loads(gpt_raw_output)
            print("\n🧠 [GPT-4 Strategy Output for Comparison Only]:")
            print(json.dumps(gpt_strategy, indent=2))

            # === 🧠 Auto-patch straddle/strangle based on explanation text ===
            explanation = gpt_strategy.get("explanation", "").lower()

            if "straddle" in explanation and "call" in explanation and "put" in explanation:
                print("🛠️ Auto-patching strategy as STRADDLE")
                gpt_strategy["type"] = "Straddle"
                gpt_strategy["trade_legs"] = ["buy 1 ATM call", "buy 1 ATM put"]

            elif "strangle" in explanation and "call" in explanation and "put" in explanation:
                print("🛠️ Auto-patching strategy as STRANGLE")
                gpt_strategy["type"] = "Strangle"
                gpt_strategy["trade_legs"] = ["buy 1 OTM call", "buy 1 OTM put"]

            strategy = gpt_strategy
            strategy["source"] = "gpt_json"
            strategy["explanation"] = generate_strategy_explainer(belief, strategy)


        except json.JSONDecodeError:
            print("[⚠️ Fallback] GPT returned invalid JSON, attempting soft parse...")

            soft_strategy = attempt_gpt_strategy_parse(
                belief,
                gpt_raw_output,
                {
                    "ticker": ticker,
                    "direction": direction,
                    "tags": tags,
                    "asset_class": asset_class,
                    "goal_type": goal_type,
                    "multiplier": multiplier,
                    "timeframe": timeframe,
                    "risk_profile": risk_profile,
                    "confidence": confidence,
                    "price_info": price_info,
                },
            )

            if soft_strategy:
                print("[✅ Soft Parser] Recovered strategy from GPT prose.")
                strategy = soft_strategy
                strategy["source"] = "gpt_soft_parse"
            else:
                print("[❌ Soft Parser] Failed to extract strategy from prose. Using ML fallback.")
                from backend.ai_engine.ml_strategy_bridge import run_ml_strategy_model

                strategy = run_ml_strategy_model(
                    belief,
                    {
                        "direction": direction,
                        "ticker": ticker,
                        "tags": tags,
                        "asset_class": asset_class,
                        "goal_type": goal_type,
                        "multiplier": multiplier,
                        "timeframe": timeframe,
                        "risk_profile": risk_profile,
                        "confidence": confidence,
                        "price_info": price_info,
                    },
                )
                
                strategy["explanation"] = generate_strategy_explainer(belief, strategy)



    except Exception as e:
        print(f"[GPT DEBUG] ❌ GPT strategy generation failed: {e}")


    # === 🧠 Clean up expiration
    if asset_class == "options":
        strategy["expiration"] = fix_expiration(ticker, strategy.get("expiration"))


    # ✅ FIXED: Ensure trade_legs list is converted to a lowercase string safely
    strategy_type = strategy.get("type", "").lower()
    trade_legs_raw = strategy.get("trade_legs", [])
    trade_legs = " ".join(str(leg).lower() for leg in trade_legs_raw)

    tags = []
    if "spread" in strategy_type or "spread" in trade_legs:
        if "put" in trade_legs and "sell" in trade_legs and "buy" in trade_legs:
            tags.append(
                "bear put spread"
                if direction == "bearish"
                else "bull put spread"
            )
        elif (
            "call" in trade_legs
            and "sell" in trade_legs
            and "buy" in trade_legs
        ):
            tags.append(
                "bull call spread"
                if direction == "bullish"
                else "bear call spread"
            )
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

    if direction == "neutral" and "long call" in tags:
        direction = "bullish"
    elif direction == "neutral" and "long put" in tags:
        direction = "bearish"

    explanation = strategy.get(
        "explanation", "Strategy explanation not available."
    )
    log_strategy(belief, explanation, user_id, strategy)

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
            "notes": f"Validation error: {e}",
        }

    # ✅ FINAL FIX: Ensure explanation is set if missing (e.g. GPT timeout cases)
    if "explanation" not in strategy or not isinstance(strategy["explanation"], str) or not strategy["explanation"].strip():
        print("⚠️ Explanation missing — generating now via fallback GPT call...")
        try:
            fallback_explainer = generate_strategy_explainer(belief, strategy)

            explanation_str = None
            if isinstance(fallback_explainer, dict):
                explanation_str = fallback_explainer.get("explanation") if isinstance(fallback_explainer, dict) else str(fallback_explainer)
            elif isinstance(fallback_explainer, str):
                explanation_str = fallback_explainer

            if explanation_str and isinstance(explanation_str, str):
                strategy["explanation"] = explanation_str
            else:
                strategy["explanation"] = "Strategy explanation not available."

            print("✅ [Auto Explanation Injected]")
        except Exception as e:
            print(f"[❌] Explanation generation failed: {e}")
            strategy["explanation"] = f"Explanation unavailable due to error: {e}"



    # ✅ DEBUG — Log final strategy output for visibility
    print("[DEBUG] Final strategy output:")
    print(
        json.dumps(
            {
                "strategy": strategy,
                "ticker": ticker,
                "asset_class": asset_class,
                "tags": tags,
                "direction": direction,
                "price_info": price_info,
                "high_low": [clean_float(high_low[0]), clean_float(high_low[1])],
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
            },
            indent=2,
        )
    )
    # Add dynamic fields based on asset class
    print("🔍 CHECKPOINT: About to add dynamic fields!")
    asset_specific_fields = add_dynamic_fields(asset_class, strategy, ticker, price_info)
    
    return {
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": [clean_float(high_low[0]), clean_float(high_low[1])],
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
        **asset_specific_fields
    }

# === 🎯 DYNAMIC ASSET-SPECIFIC FIELDS ===
# FILE: backend/ai_engine/ai_engine.py (lines 537-580 replacement)

def add_dynamic_fields(asset_class: str, strategy: dict, ticker: str, price_info: dict) -> dict:
    """
    Add asset-specific fields based on asset class.
    CLEANED VERSION: Removed fake Greeks and amateur hardcoded values.
    Only includes real, meaningful data that adds value.
    """
    dynamic_fields = {}
    
    if asset_class == "options":
        # Options-specific fields - REAL DATA ONLY
        dynamic_fields.update({
            "strike_price": strategy.get("strike_price", "ATM"),
            "max_profit": strategy.get("target_return", "Unlimited"),
            "max_loss": strategy.get("max_loss", "Premium Paid"),
            "expiration": strategy.get("expiration", "TBD"),
            "option_type": strategy.get("trade_legs", [{}])[0].get("option_type", "Call") if strategy.get("trade_legs") else "Call"
        })
        
    elif asset_class == "equity" or asset_class == "stock":
        # Stock-specific fields - MEANINGFUL DATA
        current_price = price_info.get('latest', 0)
        if current_price > 0:  # Only calculate if we have real price data
            dynamic_fields.update({
                "entry_price": f"${current_price:.2f}",
                "target_price": f"${current_price * 1.15:.2f}",  # 15% target
                "stop_loss": f"${current_price * 0.90:.2f}",     # 10% stop
                "position_size": "To be determined",
                "risk_reward_ratio": "1:1.5"
            })
            
    elif asset_class == "bonds" or asset_class == "bond":
        # Bond-specific fields - PLACEHOLDER (until real bond data integration)
        dynamic_fields.update({
            "yield": "Market rate",
            "duration": "TBD",
            "maturity_date": "TBD",
            "credit_rating": "To be analyzed"
        })
        
    elif asset_class == "crypto":
        # Crypto-specific fields - PLACEHOLDER (until crypto integration)
        current_price = price_info.get('latest', 0)
        if current_price > 0:
            dynamic_fields.update({
                "volatility": "High",
                "24h_volume": "Check exchange",
                "market_cap": "Variable"
            })
    
    # Return only meaningful fields, no fake Greeks
    return dynamic_fields

# === 🔒 Helper Function: Safe JSON serialization ===
def safe_json(data):
    """Recursively sanitize data for JSON compliance (NaN → None, etc)."""
    def fix_value(val):
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return None
        return val

    if isinstance(data, dict):
        return {k: safe_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [safe_json(item) for item in data]
    else:
        return fix_value(data)


# === 🧠 New Function: Asset Basket Generation via GPT-4 ===
def generate_asset_basket(
    input_text: str, goal: Optional[str] = None, user_id: Optional[str] = None
) -> dict:
    """
    Generates an intelligent asset basket (stocks, bonds, crypto, etc.)
    based on user input using GPT-4. Returns a parsed JSON structure.
    """
    try:
        prompt = f"""
        You are a financial advisor AI.

        A user has requested a smart asset allocation basket.
        Their input: "{input_text}"
        Goal: {goal or "unspecified"}

        Your task:
            - Create a diversified basket of 2–5 assets (stocks, ETFs, crypto, bonds).
            - For each: include ticker, type, allocation %, and a one-sentence rationale.
            - Also return a goal summary, estimated return range, and risk profile.

            Format as valid JSON:
                {{
                "basket": [
                {{
                "ticker": "VTI",
                "type": "stock",
                "allocation": "60%",
                "rationale": "Broad U.S. stock exposure"
                }},
                {{
                "ticker": "BND",
                "type": "bond",
                "allocation": "40%",
                "rationale": "Diversified bond exposure"
                }}
                ],
                "goal": "moderate growth",
                "estimated_return": "5–7% annually",
                "risk_profile": "moderate"
                }}

                Only return pure JSON — no explanation, markdown, or commentary.
                """

        print("📦 Calling GPT-4 for asset basket generation...")

        response = get_openai_client().chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500,
        )

        raw_output = response.choices[0].message.content.strip()
        print("🧠 Raw GPT Output:\n", raw_output)

        try:
            # ✅ Attempt to parse GPT output into JSON
            parsed = json.loads(raw_output)
            # ✅ STEP 1 — Sanitize and validate basket items
            if "basket" in parsed and isinstance(parsed["basket"], list):
                clean_basket = []
                seen_tickers = set()

                for item in parsed["basket"]:
                    ticker = item.get("ticker", "").strip().upper()
                    alloc = item.get("allocation", "").strip().replace("%", "")

                    if not ticker or not alloc or not alloc.replace(".", "").isdigit():
                        print(f"[❌ INVALID] Skipping malformed item: {item}")
                        continue

                    if ticker in seen_tickers:
                        print(f"[⚠️ DUPLICATE] Skipping duplicate ticker: {ticker}")
                        continue

                    seen_tickers.add(ticker)
                    clean_basket.append(item)

                parsed["basket"] = clean_basket
                print(f"[✅ CLEANED] Final basket: {parsed['basket']}")
            else:
                print(f"[❌ ERROR] No valid basket structure returned.")
                parsed["basket"] = []

            # ✅ Apply safety conversion (fix None, NaN, etc.)
            return safe_json(parsed)

        except json.JSONDecodeError as e:
            # ❌ Catch and log any failure in parsing GPT's response
            print(f"❌ JSON Decode Error in GPT response: {e}")
            # ✅ Return safe fallback instead of crashing the app
            return {
                "basket": [],
                "error": "Invalid GPT output — failed to parse."
            }

    except Exception as e:
        print(f"[❌] GPT-4 asset basket generation failed: {e}")

        # Fallback conservative basket
        return {
            "basket": [
                {
                    "ticker": "VTI",
                    "type": "stock",
                    "allocation": "60%",
                    "rationale": "Broad U.S. stock exposure for long-term growth",
                },
                {
                    "ticker": "BND",
                    "type": "bond",
                    "allocation": "40%",
                    "rationale": "Bond ETF for income and capital preservation",
                },
            ],
            "goal": goal or "growth",
            "estimated_return": "4–6% annually",
            "risk_profile": "moderate",
        }


# === FIXED: New Function: Unified Trading Strategy Generator (ML + GPT + Logging) ===
def generate_trading_strategy(belief: str, user_id: str = "anonymous") -> dict:
    """
    Generates a full trading strategy from a belief using the existing run_ai_engine function.
    This is a simplified wrapper that uses the working components.
    """
    try:
        # Use the existing working run_ai_engine function
        result = run_ai_engine(belief, "moderate", user_id)
        print("✅ Strategy successfully generated and logged.")
        return result

    except Exception as e:
        print(f"❌ generate_trading_strategy failed: {e}")
        return {
            "error": f"Strategy generation failed: {e}",
            "strategy": None,
            "user_id": user_id
        }


print("✅ ai_engine.py fully loaded")

# ✅ For test visibility
print(f"📤 [ai_engine.py] generate_trading_strategy = {generate_trading_strategy}")

# ✅ Optional: limit __all__ export scope
__all__ = ["generate_trading_strategy", "run_ai_engine", "generate_asset_basket"]