# backend/ai_engine/ai_engine.py
print(" ai_engine.py: Top of file loaded.")

"""
Main AI Engine " Translates beliefs into trade strategies.
Includes GPT-4 integration, goal parsing, bond logic, robust fallback handling.
Now with automatic creative mapping decision (no more port-based routing).
"""
import time
import re
import os
import json
import math
from backend.risk_management.position_sizing import add_risk_management_to_strategy
from datetime import datetime
from openai import OpenAI, OpenAIError
import openai
from backend.ai_engine.strategy_explainer import generate_strategy_explainer

print("ai_engine.py: All imports finished.")



from typing import Optional
from backend.openai_config import OPENAI_API_KEY, GPT_MODEL
print(" Imported openai_config")

from backend.belief_parser import parse_belief
print(" Imported belief_parser")

from backend.market_data import (
    get_latest_price,
    get_weekly_high_low,
    get_option_expirations,
)
print(" Imported market_data")

from backend.ai_engine.goal_evaluator import (
    evaluate_goal_from_belief as evaluate_goal,
)
print(" Imported goal_evaluator")

from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
print(" Imported expiry_utils")

from backend.logger.strategy_logger import log_strategy
print(" Imported strategy_logger")

from backend.ai_engine.strategy_model_selector import decide_strategy_engine
print(" Imported strategy_model_selector")

from backend.utils.symbol_universe import is_tradable_symbol, normalize_ticker



if not OPENAI_API_KEY:
    raise ValueError(" OPENAI_API_KEY not found in environment variables.")
else:
    print(f"OpenAI key loaded: ...{OPENAI_API_KEY[-4:]}")


    openai.api_key = OPENAI_API_KEY

    client = None  # Will be initialized lazily later
    print(" [Debug] OpenAI client set to None (lazy init ready)")

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


 # === " Lazy Load Helper: Create OpenAI client only when needed ===
client = None
print(" [Debug] OpenAI client set to None (lazy init ready)")

def get_openai_client():
    """
    Lazily initializes the OpenAI client only when called.
    Prevents backend hangs or timeouts on startup.
    """
    global client
    if client is None:
        try:
            client = OpenAI()  #  not get_openai_client()
        except OpenAIError as e:
            raise RuntimeError(f" Failed to initialize OpenAI Client: {e}")
    return client



# ===   Helper: Parse GPT output into structured strategy ===
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
      Soft fallback GPT strategy parser " uses keyword-based recovery from natural language output.
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
        print(" [Soft Parser] Recovered strategy from GPT prose.")
        strategy["source"] = "gpt_soft_parse"
        return strategy

    print("[ Soft Parser] Failed to extract strategy from prose.")
    return None

# === JSON hardening helpers ===
def coerce_json(s):
    """
    Accepts str or dict. If a str has markdown fences or extra prose,
    remove the fences and extract the first {} JSON block.
    """
    if isinstance(s, dict):
        return s
    if not isinstance(s, str):
        raise TypeError("coerce_json expects str or dict")

    # Remove ```json fences and plain ```
    cleaned = re.sub(r"```(?:json)?|```", "", s).strip()

    # Attempt to find the first complete JSON object in the cleaned string
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            pass

    # Fallback: try to parse the entire cleaned string
    return json.loads(cleaned)

def parse_strategy_json(payload):
    """
    Robustly parse OpenAI output that may be a dict or a string with fences.
    Returns a Python dict or raises on unrecoverable errors.
    """
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return coerce_json(payload)
    raise TypeError("parse_strategy_json received unsupported type")


def _guard_spurious_ticker(belief_text: str, ticker: str) -> str:
    """
    Prevent English words (e.g., 'next', 'on', 'all', 'tour') from slipping in as tickers
    when they appear as lowercase nouns in the belief.
    Rule: if the candidate equals a common word found in the belief in lowercase,
    and the belief does NOT contain the ticker as an uppercase token or as $TICKER, reject it.
    """
    try:
        t = (ticker or "").strip().upper()
        if not t:
            return "SPY"

        b = f" {belief_text or ''} "
        b_lower = b.lower()

        # Common words that are also tickers
        common_words = {"NEXT", "S", "ON", "ALL", "TOUR"}

        # Helper checks
        def has_uppercase_token(word: str) -> bool:
            return f" {word} " in b or f"({word})" in b or f"[{word}]" in b

        def has_dollar_ticker(word: str) -> bool:
            return f"${word}" in b

        # Block if common word is present in lowercase in the belief
        if (
            t in common_words
            and f" {t.lower()} " in b_lower
            and not has_uppercase_token(t)
            and not has_dollar_ticker(t)
        ):
            print(f"[GUARD] Spurious ticker '{t}' inferred from common word in belief; defaulting to SPY")
            return "SPY"

        return t
    except Exception as e:
        print(f"[GUARD ERROR] {e}")
        return ticker or "SPY"


def _maybe_nudge_to_bull_call_spread(strategy: dict, belief: str, price_info: dict) -> dict:
    """
    If belief contains an explicit % and timeframe (weeks/months/quarter) and the current
    strategy is a single long call, nudge to a bull call spread using spot-based strikes.
    SANE + SURGICAL: only adjusts if it looks like underperformance risk.
    """
    try:
        if not isinstance(strategy, dict):
            return strategy

        s_type = (strategy.get("type") or "").lower()
        legs = strategy.get("trade_legs") or []
        if "call option" not in s_type or not legs:
            return strategy  # only touch simple long-call outputs

        import re
        pct = None
        m = re.search(r'(\d{1,2})\s*%|\~\s*(\d{1,2})\s*%', belief)
        if m:
            pct = float(m.group(1) or m.group(2))
        short_tf = re.search(r'(week|weeks|month|months|quarter)', belief.lower()) is not None
        if not (pct and short_tf):
            return strategy

        spot_raw = price_info.get("latest")
        try:
            spot = float(spot_raw)
        except Exception:
            return strategy
        if spot <= 0:
            return strategy

        if not (len(legs) == 1 and isinstance(legs[0], dict) and legs[0].get("option_type","").lower()=="call"):
            return strategy

        def round_like(underlying):
            return 5 if underlying >= 100 else 1

        step = round_like(spot)
        def round_to(v, step):
            return step * round(float(v)/step)

        buy_strike = round_to(spot, step)
        target = spot * (1 + min(max(pct, 3), 20)/100.0)  # clamp 3%..20%
        sell_strike = max(buy_strike + step, round_to(target, step))

        expiry = strategy.get("expiration") or legs[0].get("expiration") or "TBD"
        sym = legs[0].get("ticker") or "SPY"

        new_legs = [
            {"action": "Buy to Open", "ticker": sym, "option_type": "Call", "strike_price": str(buy_strike), "expiration": expiry},
            {"action": "Sell to Open", "ticker": sym, "option_type": "Call", "strike_price": str(sell_strike), "expiration": expiry},
        ]
        out = {**strategy, "type": "Bull Call Spread", "trade_legs": new_legs}
        if "target_return" in out:
            out["target_return"] = "20-40%"
        if "max_loss" in out:
            out["max_loss"] = "Net Debit"
        return out
    except Exception as e:
        print(f"[NUDGE ERROR] {e}")
        return strategy

 # ===   Helper: Nudge long put ' Bear Put Spread (short timeframe + % drop) ===
def _maybe_nudge_to_bear_put_spread(strategy: dict, belief: str, price_info: dict) -> dict:
    """
    If belief contains an explicit % drop and short timeframe (weeks/months)
    and current strategy is a single long put, nudge to a bear put spread using spot-based strikes.
    """
    try:
        if not isinstance(strategy, dict):
            return strategy

        s_type = (strategy.get("type") or "").lower()
        legs = strategy.get("trade_legs") or []
        # only touch simple long-put outputs (1 leg, PUT)
        if "put option" not in s_type or len(legs) != 1:
            return strategy
        leg = legs[0] if isinstance(legs[0], dict) else {}
        if str(leg.get("option_type", "")).lower() != "put":
            return strategy

        import re
        pct = None
        m = re.search(r'(\d{1,2})\s*%|\~\s*(\d{1,2})\s*%', belief)
        if m:
            pct = float(m.group(1) or m.group(2))
        short_tf = re.search(r'(week|weeks|month|months)', belief.lower()) is not None
        if not (pct and short_tf):
            return strategy

        spot_raw = price_info.get("latest")
        try:
            spot = float(spot_raw)
        except Exception:
            return strategy
        if spot <= 0:
            return strategy

        # Round strikes sensibly (5 for large prices like NVDA/SPY; else 1)
        step = 5 if spot >= 100 else 1
        def round_to(v, step): 
            return step * round(float(v)/step)

        # Bear put: BUY higher strike (near spot), SELL lower strike (near target drop)
        buy_strike  = round_to(spot, step)
        drop_clamped = max(3.0, min(20.0, pct))  # clamp 3"20%
        target_down = spot * (1 - drop_clamped/100.0)
        sell_strike = min(buy_strike - step, round_to(target_down, step))

        sym    = leg.get("ticker") or "NVDA"
        expiry = strategy.get("expiration") or leg.get("expiration") or "TBD"

        new_legs = [
            {"action": "Buy to Open",  "ticker": sym, "option_type": "Put", "strike_price": str(buy_strike),  "expiration": expiry},
            {"action": "Sell to Open", "ticker": sym, "option_type": "Put", "strike_price": str(sell_strike), "expiration": expiry},
        ]

        out = {**strategy, "type": "Bear Put Spread", "trade_legs": new_legs}
        out["max_loss"] = "Net Debit"
        out["target_return"] = out.get("target_return") or "20-40%"
        return out
    except Exception as e:
        print(f"[BEAR NUDGE ERROR] {e}")
        return strategy
       

# ===   Helper: Sanitize Spread Strikes ===
def _sanitize_spread_strikes(strategy: dict, belief: str, price_info: dict) -> dict:
    """
    If we already have a call spread but strikes are clearly unrealistic vs spot
    (e.g., SPY ~645 but strikes are 19/20), recalc to sane spot-based levels.
    """
    try:
        if not isinstance(strategy, dict):
            return strategy
        s_type = (strategy.get("type") or "").lower()
        legs = strategy.get("trade_legs") or []
        if "spread" not in s_type or len(legs) != 2:
            return strategy

        def _to_float(v):
            try:
                return float(str(v).replace("$","").strip())
            except Exception:
                return None

        call_legs = [leg for leg in legs if isinstance(leg, dict) and str(leg.get("option_type","")).lower()=="call"]
        if len(call_legs) != 2:
            return strategy

        s1 = _to_float(call_legs[0].get("strike_price"))
        s2 = _to_float(call_legs[1].get("strike_price"))
        if s1 is None or s2 is None:
            return strategy

        spot_raw = price_info.get("latest")
        try:
            spot = float(spot_raw)
        except Exception:
            return strategy
        if spot <= 0:
            return strategy

        low_thresh = 0.5 * spot
        high_thresh = 5.0 * spot
        unrealistic = (s1 < low_thresh and s2 < low_thresh) or (s1 > high_thresh and s2 > high_thresh)
        if not unrealistic:
            return strategy

        import re
        pct = 5.0
        m = re.search(r'(\d{1,2})\s*%|\~\s*(\d{1,2})\s*%', str(belief))
        if m:
            try:
                pct = float(m.group(1) or m.group(2))
            except Exception:
                pass
        pct = max(3.0, min(20.0, pct))

        def step_for(x): return 5 if x >= 100 else 1
        step = step_for(spot)
        def round_to(v, step): return step * round(float(v)/step)

        buy = round_to(spot, step)
        sell = max(buy + step, round_to(spot * (1.0 + pct/100.0), step))

        sym = call_legs[0].get("ticker") or call_legs[1].get("ticker") or "SPY"
        expiry = strategy.get("expiration") or call_legs[0].get("expiration") or call_legs[1].get("expiration") or "TBD"

        new_legs = [
            {"action": "Buy to Open",  "ticker": sym, "option_type": "Call", "strike_price": str(buy),  "expiration": expiry},
            {"action": "Sell to Open", "ticker": sym, "option_type": "Call", "strike_price": str(sell), "expiration": expiry},
        ]
        out = {**strategy, "trade_legs": new_legs}

        if "bull" not in s_type and "call" in s_type:
            out["type"] = "Bull Call Spread"
        if "max_loss" in out:
            out["max_loss"] = "Net Debit"
        if "target_return" in out:
            out["target_return"] = "20-40%"

        print(f"[SANITIZE] Spread strikes corrected from {s1}/{s2} to {buy}/{sell} (spot ~ {spot})")
        return out
    except Exception as e:
        print(f"[SANITIZE ERROR] {e}")
        return strategy


# ===   Helper: Normalize Bear Put Spread Type + Explanation ===
def _normalize_bear_put_spread(strategy: dict) -> dict:
    """
    If the strategy is a 2-leg put spread, normalize its type to 'Bear Put Spread'
    and fix key fields/explanation to match puts (not calls).
    """
    try:
        if not isinstance(strategy, dict):
            return strategy
        legs = strategy.get("trade_legs") or []
        if len(legs) != 2:
            return strategy

        # Both legs must be puts
        def _is_put(leg):
            return isinstance(leg, dict) and str(leg.get("option_type", "")).lower() == "put"

        put_legs = [leg for leg in legs if _is_put(leg)]
        if len(put_legs) != 2:
            return strategy

        # Extract strikes
        def _to_f(x):
            try:
                return float(str(x).replace("$", "").strip())
            except Exception:
                return None

        s1 = _to_f(put_legs[0].get("strike_price"))
        s2 = _to_f(put_legs[1].get("strike_price"))
        if s1 is None or s2 is None:
            return strategy

        sym = put_legs[0].get("ticker") or put_legs[1].get("ticker") or "?"
        lo, hi = sorted([s1, s2])  # bear put typically: BUY higher, SELL lower
        out = {**strategy}

        # Normalize type/labels
        out["type"] = "Bear Put Spread"
        # Economics text
        out["max_loss"] = "Net Debit"
        out["target_return"] = out.get("target_return") or "20-40%"

        # Clean explanation to match puts
        out["explanation"] = f"Bear Put Spread on {sym} between {hi} and {lo}. Limits loss to net debit and caps profit at the spread width. Profits if price trends down toward the lower strike by expiry."

        return out
    except Exception as e:
        print(f"[PUT NORMALIZE ERROR] {e}")
        return strategy


# ===  Helper: Infer Tags From Final Strategy ===
def _infer_tags_from_strategy(strategy: dict, direction: str) -> list:
    tl = " ".join(str(leg).lower() for leg in strategy.get("trade_legs", []))
    st = (strategy.get("type") or "").lower()
    tags = []
    if "spread" in st or "spread" in tl:
        if "call" in tl:
            tags.append("bull call spread" if direction == "bullish" else "bear call spread")
        elif "put" in tl:
            tags.append("bear put spread" if direction == "bearish" else "bull put spread")
        else:
            tags.append("spread")
    elif "call" in st:
        tags.append("long call" if "buy" in tl else "call")
    elif "put" in st:
        tags.append("long put" if "buy" in tl else "put")
    elif "equity" in st or "stock" in st:
        tags.append("stock")
    elif "straddle" in st or "strangle" in st:
        tags.append("neutral")
    return tags

# ===  Helper: Sanitize explanation to match final strategy ===
def _sanitize_explanation(strategy: dict, price_info: dict) -> str:
    """
    Rewrite explanation so it matches the FINAL legs/type.
    Detects Call-vs-Put spreads and names them correctly.
    """
    try:
        expl = strategy.get("explanation", "")
        legs = strategy.get("trade_legs", [])
        st = (strategy.get("type") or "").lower()
        if not legs or len(legs) not in (1, 2):
            return expl

        # Identify leg types
        def _leg_type(l):
            return str(l.get("option_type", "")).lower() if isinstance(l, dict) else ""

        calls = [l for l in legs if _leg_type(l) == "call"]
        puts  = [l for l in legs if _leg_type(l) == "put"]

        # One-leg cases: leave original text
        if len(legs) == 1:
            return expl

        # Two-leg spreads
        if len(legs) == 2 and (calls or puts):
            s1 = legs[0].get("strike_price")
            s2 = legs[1].get("strike_price")
            sym = legs[0].get("ticker") or legs[1].get("ticker") or "?"
            lo, hi = (s1, s2)

            if len(calls) == 2:
                label = "Bull Call Spread"
            elif len(puts) == 2:
                label = "Bear Put Spread"
                try:
                    f1, f2 = float(s1), float(s2)
                    hi, lo = (str(max(f1, f2)), str(min(f1, f2)))
                except Exception:
                    hi, lo = (s1, s2)
            else:
                label = "Spread"

            return f"{label} on {sym} between {hi} and {lo}. Limits loss to net debit and caps profit at the spread width."

        return expl
    except Exception as e:
        print(f"[SANITIZE EXPLAIN ERROR] {e}")
        return strategy.get("explanation", "")





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
                print(f"[FIXED] Overriding bad expiration ' {future_dates[0]}")
                return future_dates[0]
            else:
                print("[WARNING] No valid expirations found. Using 'N/A'.")
                return "N/A"
        return raw_expiry
    except Exception as e:
        print(f"[ERROR] Expiration fix failed: {e}")
        return "N/A"


def _should_try_creative(parsed: dict, belief: str) -> bool:
    """Determine if we should try creative mapping for this ticker."""
    sym = parsed.get("ticker")
    
    # Missing or generic
    if not sym or str(sym).upper() in {"SPY", "QQQ"}:
        return True
    
    # Spurious common words
    COMMON_WORDS = {"NEXT", "S", "ON", "ALL", "TOUR", "WORK", "ALLY", "LOVE"}
    sym_upper = str(sym).upper()
    belief_lower = belief.lower()
    if sym_upper in COMMON_WORDS and f" {sym.lower()} " in f" {belief_lower} " and f" {sym_upper} " not in f" {belief} " and f"${sym_upper}" not in belief:
        return True
    
    # Not tradable
    if not is_tradable_symbol(normalize_ticker(sym)):
        return True
    
    return False

def should_use_creative(parsed: dict, belief: str) -> bool:
    """
    Intelligently decide if creative mapping should be used based on belief characteristics.
    This unifies the system to a single backend instead of port-based routing (8000 vs 8001).
    
    Returns True if:
    - CREATIVE_MAPPING_ENABLED env var is set to "true" (default false)
    - No valid ticker detected or only generic tickers (SPY, QQQ, DIA)
    - Tags are empty or too vague
    - Belief is thematic/cultural (contains key phrases)
    """
    # Check CREATIVE_MAPPING_ENABLED env var (default to "false")
    creative_enabled = os.getenv("CREATIVE_MAPPING_ENABLED", "false").lower() == "true"
    if creative_enabled:
        print("[CREATIVE] Enabled via CREATIVE_MAPPING_ENABLED=true env var")
        return True
    
    # Check ticker quality
    ticker = parsed.get("ticker", "").upper()
    if not ticker or ticker in {"SPY", "QQQ", "DIA", "IWM", ""}:
        print(f"[CREATIVE] Generic/missing ticker detected: '{ticker}'")
        return True
    
    # Check tag quality
    tags = parsed.get("tags", [])
    if not tags or all(t in {"options", "equity", "etf", "stock"} for t in tags):
        print(f"[CREATIVE] Vague/empty tags detected: {tags}")
        return True
    
    # Check for thematic/cultural keywords that suggest creative interpretation needed
    thematic_keywords = [
        "why", "markets", "nervous", "boom", "culture", "trend", 
        "sentiment", "everyone", "nobody", "viral", "meme", "hype",
        "fear", "greed", "panic", "euphoria", "bubble", "crash"
    ]
    belief_lower = belief.lower()
    if any(kw in belief_lower for kw in thematic_keywords):
        print(f"[CREATIVE] Thematic/cultural belief detected")
        return True
    
    print(f"[CREATIVE] Not needed - ticker: {ticker}, tags: {tags}")
    return False


def run_ai_engine(
    belief: str, risk_profile: str = "moderate", user_id: str = "anonymous"
) -> dict:
    start_time = time.time()
    parsed = parse_belief(belief)
    
    # --- Creative Mapping: Automatic decision based on belief characteristics ---
    # This replaces port-based routing (8000 vs 8001) with intelligent detection
    use_creative = should_use_creative(parsed, belief)
    print(f"[DEBUG] Creative mapping decision: {use_creative} (ticker={parsed.get('ticker')})")
    
    if use_creative:
        try:
            from backend.signal_mapping.creative_mapper import (
                generate_symbol_candidates,
                choose_best_candidate,
            )
            cands = generate_symbol_candidates(belief)
            best = choose_best_candidate(cands)
            if best:
                parsed["ticker"] = best["symbol"]
                ticker = parsed["ticker"]  # Update local variable immediately
                print(f"[CREATIVE MAPPING] Applied: {best['symbol']} (score={best['score']})")
                parsed.setdefault("tags", []).append("creative-mapped")
                parsed.setdefault("explanation_notes", []).append(
                    f"Creative mapping: {best['symbol']} (score={best['score']}). {best.get('why','')}"
                )
            else:
                print("[CREATIVE MAPPING] No suitable candidates found, keeping original")
        except Exception as e:
            print(f"[CREATIVE MAPPING] Error: {e}")
    # --- end Creative Mapping ---

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

    #   Fallback logic if no ticker was detected from belief
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"  # Safe fallback

    #  Properly assign asset class after ticker is finalized
    if parsed_asset == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    elif parsed_asset == "bond" and ticker.upper() == "SPY":
        asset_class = "bond"
        ticker = "TLT"  # Safer fallback for bond beliefs
    else:
        asset_class = parsed_asset
        ticker = _guard_spurious_ticker(belief, ticker)


    from backend.utils.symbol_universe import is_tradable_symbol, normalize_ticker

    #  Get price data safely (skip non-tradables like SWIFT/BLACK)
    try:
        assert is_tradable_symbol(normalize_ticker(ticker)), f"Non-tradable: {ticker}"
        latest = get_latest_price(ticker)
    except Exception as e:
        print(f"[ERROR] get_latest_price failed: {e}")
        latest = -1.0

    try:
        assert is_tradable_symbol(normalize_ticker(ticker)), f"Non-tradable: {ticker}"
        high_low = get_weekly_high_low(ticker)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low failed: {e}")
        high_low = (-1.0, -1.0)
    

    #  Normalize price data
    price_info = {
        "latest": clean_float(latest),
        "high": clean_float(high_low[0]),
        "low": clean_float(high_low[1]),
    }

    #  Detect if this is a bond ladder-style belief
    bond_tags = ["bond", "ladder", "income", "fixed income"]
    is_bond_ladder = (
        "bond ladder" in belief.lower()
        or any(tag in tags for tag in bond_tags)
        or asset_class == "bond"
    )

    #  Construct the base prompt for GPT strategy generation
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

    # ===  NEW: Route strategy generation through hybrid GPT/ML selector ===
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
    
    #  CRITICAL PRODUCTION FIX: Check if sentiment validation blocked the strategy
    if strategy is None:
        print(" STRATEGY BLOCKED: Sentiment validation prevented misaligned strategy")
        return {
            "error": "Strategy blocked due to sentiment misalignment",
            "strategy": None,
            "ticker": ticker,
            "direction": direction,
            "user_id": user_id,
            "processing_time": time.time() - start_time,
            "reason": "Bullish belief cannot generate neutral/bearish strategies in production mode"
        }

        # ===  GPT CALL GUARD =======================================================
    # Only call GPT here if we *need* it:
    #   - No strategy yet (strategy is None), OR
    #   - The selector returned an ML-based strategy (source starts with "ml"),
    #     in which case we allow GPT to augment/replace once.
    # This prevents duplicate "Sending belief to GPT-4..." calls per request.
    _should_call_gpt = (
        strategy is None
        or (isinstance(strategy, dict) and str(strategy.get("source", "")).lower().startswith("ml"))
    )
    # ============================================================================

    # === " Soft Fallback Parser Injection for GPT-4 ===
    if _should_call_gpt:
        try:
            from backend.ai_engine.gpt4_strategy_generator import generate_strategy_with_validation

            # Get sentiment from belief parser for validation
            detected_sentiment = direction  # Use the direction already parsed above
            gpt_raw_output = generate_strategy_with_validation(belief, detected_sentiment)

            try:
                gpt_strategy = parse_strategy_json(gpt_raw_output)
                print("\n  [GPT-4 Strategy Output for Comparison Only]:")
                print(json.dumps(gpt_strategy, indent=2))

                # ===   Auto-patch straddle/strangle based on explanation text ===
                explanation = gpt_strategy.get("explanation", "").lower()
                if "straddle" in explanation and "call" in explanation and "put" in explanation:
                    print("  Auto-patching strategy as STRADDLE")
                    gpt_strategy["type"] = "Straddle"
                    gpt_strategy["trade_legs"] = ["buy 1 ATM call", "buy 1 ATM put"]
                elif "strangle" in explanation and "call" in explanation and "put" in explanation:
                    print("  Auto-patching strategy as STRANGLE")
                    gpt_strategy["type"] = "Strangle"
                    gpt_strategy["trade_legs"] = ["buy 1 OTM call", "buy 1 OTM put"]

                strategy = gpt_strategy
                strategy["source"] = "gpt_json"

                # Keep any existing string explanation; normalize dict ' string to avoid .get() errors
                if isinstance(strategy.get("explanation"), dict):
                    strategy["explanation"] = json.dumps(strategy["explanation"])

                try:
                    _expl = generate_strategy_explainer(belief, strategy)
                    if isinstance(_expl, dict):
                        strategy["explanation"] = str(_expl.get("explanation", _expl))
                    elif isinstance(_expl, str):
                        strategy["explanation"] = _expl
                except Exception as e:
                    print(f"[Explainer] failed: {e}")  # leave existing explanation as-is

            except json.JSONDecodeError:
                print("[  Fallback] GPT returned invalid JSON, attempting soft parse...")

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
                    print("[ Soft Parser] Recovered strategy from GPT prose.")
                    strategy = soft_strategy
                    strategy["source"] = "gpt_soft_parse"
                else:
                    print("[ Soft Parser] Failed to extract strategy from prose. Using ML fallback.")
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
            print(f"[GPT DEBUG]  GPT strategy generation failed: {e}")
    # else: skipped GPT because selector already produced a non-ML strategy




    # ===   Clean up expiration
    if asset_class == "options":
        strategy["expiration"] = fix_expiration(ticker, strategy.get("expiration"))


    #  FIXED: Ensure trade_legs list is converted to a lowercase string safely
    strategy_type = strategy.get("type", "").lower()
    trade_legs_raw = strategy.get("trade_legs", [])
    trade_legs = " ".join(str(leg).lower() for leg in trade_legs_raw)

    tags = list(tags) if isinstance(tags, list) else []
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
        print(f"[ VALIDATOR] {validation}")
    except Exception as e:
        print(f"[ERROR] Strategy validation failed: {e}")
        validation = {
            "valid": False,
            "would_profit": None,
            "estimated_profit_pct": None,
            "notes": f"Validation error: {e}",
        }

    #  FINAL FIX: Ensure explanation is set if missing (e.g. GPT timeout cases)
    if "explanation" not in strategy or not isinstance(strategy["explanation"], str) or not strategy["explanation"].strip():
        print("Explanation missing - generating now via fallback GPT call...")

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

            print(" [Auto Explanation Injected]")
        except Exception as e:
            print(f"[] Explanation generation failed: {e}")
            strategy["explanation"] = f"Explanation unavailable due to error: {e}"



    #  DEBUG " Log final strategy output for visibility
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
    print("CHECKPOINT: About to add dynamic fields!")
    asset_specific_fields = add_dynamic_fields(asset_class, strategy, ticker, price_info)

    # Nudge plain long call ' bull call spread if underperform risk
    strategy = _maybe_nudge_to_bull_call_spread(strategy, belief, price_info)

    # If it was already a spread with silly call strikes, fix them based on spot
    strategy = _sanitize_spread_strikes(strategy, belief, price_info)

    # Nudge long put ' bear put spread (short timeframe + % drop)
    strategy = _maybe_nudge_to_bear_put_spread(strategy, belief, price_info)

    # Normalize put spreads (type + explanation) if needed
    strategy = _normalize_bear_put_spread(strategy)

    # === Fix C: Ensure all trade legs use the final validated ticker ===
    # This is critical for consistency - force all legs to match
    final_ticker = ticker  # The ticker we've validated and chosen
    strategy = _normalize_strategy_ticker(strategy, final_ticker)
    print(f"[FIX C] Normalized all trade legs to use ticker: {final_ticker}")

    # ===  Final cleanup: tags + explanation ===
    existing_tags = tags if isinstance(tags, list) else []
    inferred_tags = _infer_tags_from_strategy(strategy, direction)
    tags = list({*existing_tags, *inferred_tags})  # preserve "creative-mapped"
    explanation = _sanitize_explanation(strategy, price_info)
    strategy["explanation"] = explanation

    
    # Build the result first
    result = {
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
    
    # Add risk management before returning strategy
    if result.get('strategy'):
        result = add_risk_management_to_strategy(result, user_id)
    
    return result

# ===  DYNAMIC ASSET-SPECIFIC FIELDS ===

def _normalize_strategy_ticker(strategy: dict, final_ticker: str) -> dict:
    """
    Ensure all trade legs reference the final_ticker when appropriate.
    - Keep option legs normalized to the final ticker (prevents mismatches like AAPL vs ARE).
    - Preserve per-leg instruments for bond ladders / bond-like legs (legs with maturity_date or no option_type).
    
    FIXED VERSION: Prevents KeyError on legs missing option_type.
    """
    import re
    if not strategy or not isinstance(strategy, dict):
        return strategy
    legs = strategy.get("trade_legs")
    if not legs:
        return strategy

    out = []
    stype = str(strategy.get("type", "")).lower()
    is_bond_ladder = "bond ladder" in stype

    for leg in legs:
        if isinstance(leg, str):
            # String legs (rare): for ladders, preserve as-is; for options, rewrite to final ticker heuristically
            if is_bond_ladder:
                out.append(leg)
            else:
                normalized = re.sub(r'\b[A-Z]{1,5}\b', final_ticker, leg)
                if normalized != leg:
                    print(f"[NORMALIZE] String leg: '{leg}' -> '{normalized}'")
                out.append(normalized)
            continue

        if isinstance(leg, dict):
            leg = {**leg}
            # SAFE checks: never index leg["option_type"] directly
            has_maturity = "maturity_date" in leg
            _opt = str(leg.get("option_type", "") or "").strip()
            has_option_type = _opt != ""

            if is_bond_ladder or has_maturity or not has_option_type:
                # Bond-like leg: DO NOT force its ticker; preserve instrument (e.g., UST2Y/US10Y)
                # Still ensure a ticker exists (fallback to final_ticker if missing/blank)
                if not isinstance(leg.get("ticker"), str) or not leg["ticker"].strip():
                    leg["ticker"] = final_ticker
                out.append(leg)
            else:
                # Option leg: only fill in missing ticker, don't overwrite existing valid tickers
                old = leg.get("ticker")
                if not isinstance(old, str) or not old.strip():
                    # Ticker is missing or empty, fill it with final_ticker
                    leg["ticker"] = final_ticker
                    print(f"[NORMALIZE] Filled missing ticker with: '{final_ticker}'")
                else:
                    # Keep existing ticker, don't overwrite
                    print(f"[NORMALIZE] Keeping existing ticker: '{old}'")
                out.append(leg)
            continue

        # Unknown shape: just pass through
        out.append(leg)

    return {**strategy, "trade_legs": out}



def add_dynamic_fields(asset_class: str, strategy: dict, ticker: str, price_info: dict) -> dict:
    """
    Add asset-specific fields based on asset class.
    FIXED VERSION: Safely handles missing option_type in trade_legs.
    """
    dynamic_fields = {}
    
    if asset_class == "options":
        # Options-specific fields - REAL DATA ONLY
        legs = strategy.get("trade_legs") or []
        # legs may be strings or dicts  infer option_type safely
        if legs:
            first = legs[0]
            if isinstance(first, dict):
                opt_type = str(first.get("option_type", "") or "").strip() or "Call"
            else:
                txt = str(first).lower()
                opt_type = "Put" if ("put" in txt and "call" not in txt) else "Call"
        else:
            opt_type = "Call"

        dynamic_fields.update({
            "strike_price": strategy.get("strike_price", "ATM"),
            "max_profit": strategy.get("target_return", "Unlimited"),
            "max_loss": strategy.get("max_loss", "Premium Paid"),
            "expiration": strategy.get("expiration", "TBD"),
            "option_type": opt_type
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

# === "' Helper Function: Safe JSON serialization ===
def safe_json(data):
    """Recursively sanitize data for JSON compliance (NaN ' None, etc)."""
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


# ===   New Function: Asset Basket Generation via GPT-4 ===
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
            - Create a diversified basket of 2"5 assets (stocks, ETFs, crypto, bonds).
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
                "estimated_return": "5"7% annually",
                "risk_profile": "moderate"
                }}

                Only return pure JSON " no explanation, markdown, or commentary.
                """

        print("Calling GPT-4 for asset basket generation...")

        response = get_openai_client().chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500,
        )

        raw_output = response.choices[0].message.content.strip()
        print("  Raw GPT Output:\n", raw_output)

        try:
            #  Attempt to parse GPT output into JSON
            parsed = json.loads(raw_output)
            #  STEP 1 " Sanitize and validate basket items
            if "basket" in parsed and isinstance(parsed["basket"], list):
                clean_basket = []
                seen_tickers = set()

                for item in parsed["basket"]:
                    ticker = item.get("ticker", "").strip().upper()
                    alloc = item.get("allocation", "").strip().replace("%", "")

                    if not ticker or not alloc or not alloc.replace(".", "").isdigit():
                        print(f"[ INVALID] Skipping malformed item: {item}")
                        continue

                    if ticker in seen_tickers:
                        print(f"[  DUPLICATE] Skipping duplicate ticker: {ticker}")
                        continue

                    seen_tickers.add(ticker)
                    clean_basket.append(item)

                parsed["basket"] = clean_basket
                print(f"[ CLEANED] Final basket: {parsed['basket']}")
            else:
                print(f"[ ERROR] No valid basket structure returned.")
                parsed["basket"] = []

            #  Apply safety conversion (fix None, NaN, etc.)
            return safe_json(parsed)

        except json.JSONDecodeError as e:
            #  Catch and log any failure in parsing GPT's response
            print(f" JSON Decode Error in GPT response: {e}")
            #  Return safe fallback instead of crashing the app
            return {
                "basket": [],
                "error": "Invalid GPT output - failed to parse."
            }


    except Exception as e:
        print(f"[] GPT-4 asset basket generation failed: {e}")

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
            "estimated_return": "4-6% annually",
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
        print(" Strategy successfully generated and logged.")
        return result

    except Exception as e:
        print(f" generate_trading_strategy failed: {e}")
        return {
            "error": f"Strategy generation failed: {e}",
            "strategy": None,
            "user_id": user_id
        }


print(" ai_engine.py fully loaded")

#  For test visibility
print(f"[ai_engine.py] generate_trading_strategy = {generate_trading_strategy}")

#  Optional: limit __all__ export scope
__all__ = ["generate_trading_strategy", "run_ai_engine", "generate_asset_basket"]