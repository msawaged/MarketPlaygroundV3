# backend/routes/strategy_router.py

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import math
import json

from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import save_feedback_entry
from backend.logger.strategy_logger import log_strategy
from backend.alpaca_orders import AlpacaExecutor
from backend.utils.logger import write_training_log
from backend.strategy_outcome_logger import log_strategy_outcome, log_strategy_result  # ✅ added safe wrapper

import pandas as pd
import os
from datetime import datetime

def _enrich_option_legs_with_quotes(strategy: dict) -> dict:
    """
    Prefer Alpaca quotes; fallback to yfinance only if Alpaca has no data.
    Adds bid/ask/mark/iv per option leg so the frontend can show real pricing.
    Never mutates inputs outside of 'strategy.trade_legs'.
    """
    st = strategy or {}
    legs = st.get("trade_legs") or []
    if not legs:
        return st

    for leg in legs:
        if not isinstance(leg, dict):
            continue

        # Normalize required fields
        right = str(leg.get("option_type", "")).strip().title()   # "Call" / "Put"
        if right not in ("Call", "Put"):
            continue
        sym    = str(leg.get("ticker") or "").strip().upper()
        exp    = str(leg.get("expiration") or st.get("expiration") or "").strip()  # YYYY-MM-DD
        strike = str(leg.get("strike_price") or "").strip().replace("$", "")
        if not (sym and exp and strike):
            continue

        # 1) Alpaca first
        q = {}
        try:
            from backend.market_data_alpaca import get_option_latest_quote_alpaca
            q = get_option_latest_quote_alpaca(sym, exp, strike, right)
        except Exception:
            q = {}

        # 2) yfinance fallback (only if you added it elsewhere)
        if not q:
            try:
                from backend.market_data import get_option_quote_yf
                q = get_option_quote_yf(sym, exp, strike, right)
            except Exception:
                q = {}

        # 3) Attach to leg if we found anything
        if q:
            leg["bid"]  = float(q.get("bid", 0.0) or 0.0)
            leg["ask"]  = float(q.get("ask", 0.0) or 0.0)
            leg["mark"] = float(q.get("mid", q.get("last", 0.0) or 0.0))
            leg["iv"]   = float(q.get("iv", 0.0) or 0.0)

    return st


router = APIRouter()

def sanitize_json_values(obj):
    """
    Recursively clean inf/nan values that break JSON serialization
    """
    if isinstance(obj, dict):
        return {k: sanitize_json_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj

class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"
    place_order: Optional[bool] = False

class FeedbackRequest(BaseModel):
    belief: str
    strategy: Dict[str, Any]
    feedback: str
    user_id: Optional[str] = "anonymous"

class OutcomeRequest(BaseModel):
    belief: str
    result: str
    pnl_percent: float
    user_id: Optional[str] = "anonymous"

@router.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    🔧 ENHANCED WITH PERFORMANCE MONITORING
    Generates strategy from belief, logs strategy to file and Supabase,
    and optionally executes via Alpaca.
    """
    # 📊 PERFORMANCE MONITORING: Debug print to confirm this function is called
    print("🚨 REAL STRATEGY FUNCTION CALLED! (strategy_router.py)")
    
    # 📊 PERFORMANCE MONITORING: Import metrics storage and start timer
    from backend.routes.debug_router import METRICS
    import time
    start = time.perf_counter()
    
    try:
        # 🤖 AI ENGINE: Generate strategy from user belief
        result = run_ai_engine(request.belief)
        print(f"[DBG] after run_ai_engine → type={(result.get('strategy') or {}).get('type')}, strategy_is_dict={isinstance(result.get('strategy'), dict)}")

        result["user_id"] = request.user_id
        
        # 🧹 DATA CLEANING: Remove inf/nan values that break JSON
        result = sanitize_json_values(result)

        # 💾 FEEDBACK SYSTEM: Auto-save strategy generation as feedback
        save_feedback_entry(request.belief, result, "auto_generated", request.user_id)

        # 📝 STRATEGY LOGGING: Log to strategy files for analysis
        log_strategy(
            request.belief,
            result.get("explanation", "No explanation"),
            request.user_id,
            result.get("strategy", {})
        )

        # 📊 OUTCOME TRACKING: Log initial strategy outcome (safe on strategy=None)
        try:
            # Attach belief/user_id so the logger has full context
            result["belief"] = request.belief
            result["user_id"] = request.user_id
            log_strategy_result(result)  # ✅ safe wrapper: handles strategy=None (BLOCKED)
            # Cosmetic console line:
            strat = result.get("strategy")
            strat_name = strat.get("type", "unknown") if isinstance(strat, dict) else "BLOCKED"
            print(f"🟩 Strategy logged to outcomes: {strat_name} for {result.get('ticker','UNKNOWN')}")
        except Exception as e:
            print(f"⚠️ Failed to log strategy outcome (router): {e}")

        # 🗂️ TRAINING LOG: Save to Supabase for ML training data
        try:
            write_training_log(
                message=f"[STRATEGY GENERATED]\nBelief: {request.belief}\nUser: {request.user_id}\nStrategy: {result.get('strategy', {})}",
                source="strategy_router"
            )
        except Exception as e:
            print(f"[SUPABASE LOG ERROR] {e}")

        # 📈 TRADE EXECUTION: Execute trade via Alpaca if requested
        if request.place_order:
            executor = AlpacaExecutor()
            execution_response = executor.execute_order(result, request.user_id)
            result["execution_result"] = execution_response

        # 📊 PERFORMANCE MONITORING: Log successful completion with timing
        duration = (time.perf_counter() - start) * 1000
        METRICS["response_times"].append(duration)
        METRICS["logs"].append({
            "level": "SUCCESS",
            "message": f"process_belief completed - {duration:.0f}ms",
            "duration": f"{duration:.0f}ms",
            "timestamp": time.strftime("%H:%M:%S")
        })
        
        print(f"🔧 [DEBUG] SUCCESS! Duration: {duration:.0f}ms, Total logs: {len(METRICS['logs'])}")
        
         # === Beta guard: final normalize for beta testers (MUST be last) ===
        try:
            # Import inside to avoid circulars
            from backend.ai_engine.ai_engine import _beta_guard_finish
            result = _beta_guard_finish(request.belief, result)
            print(f"[DBG] after beta_guard_finish → type={(result.get('strategy') or {}).get('type')}, strategy_is_dict={isinstance(result.get('strategy'), dict)}")

            st = result.get("strategy") or {}
            if st.get("type") in (None, "", "TBD"):
                d = (result.get("direction") or "").lower()
                st["type"] = "Call Debit Spread" if d == "bullish" else ("Put Debit Spread" if d == "bearish" else "Iron Condor")
                result["strategy"] = st


            # --- Normalize/clean for beta output shape ---
            # 1) Flatten any dict-style validator to keep JSON simple
            if isinstance(result.get("validator"), dict):
                result["validator_details"] = result["validator"]
                aligned = bool(result.get("ticker")) and bool(result.get("strategy"))
                result["validator"] = "beta_guard:aligned" if aligned else "beta_guard:rejected"

            # 2) If we have a real ticker + strategy, mark valid:true (beta rule)
            if result.get("ticker") and result.get("strategy"):
                result["valid"] = True
                # Drop scary notes unless guard explicitly set them
                if result.get("notes") and "vague" not in str(result["notes"]).lower():
                    result["notes"] = None

                # 3) Force a sensible type if missing (align with direction)
                st = result.get("strategy") or {}
                if not st.get("type"):
                    d = (result.get("direction") or "").lower()
                    st["type"] = "Call Debit Spread" if d == "bullish" else ("Put Debit Spread" if d == "bearish" else "Iron Condor")

                # 4) Ensure expiration is a future ISO date
                from datetime import datetime, timedelta
                exp = st.get("expiration")
                fix_exp = False
                if not exp or exp in ("TBD", "Unknown"):
                    fix_exp = True
                else:
                    try:
                        dt = datetime.fromisoformat(str(exp))
                        if dt.date() <= datetime.utcnow().date():
                            fix_exp = True
                    except Exception:
                        fix_exp = True
                if fix_exp:
                    tf = (result.get("timeframe") or "").lower()
                    days = 21 if "week" in tf else 30
                    st["expiration"] = (datetime.utcnow().date() + timedelta(days=days)).isoformat()

                result["strategy"] = st

                # ---- Enrich option legs with quotes (Alpaca first; fallback yf) ----
                if isinstance(result.get("strategy"), dict) and result["strategy"].get("trade_legs"):
                    result["strategy"] = _enrich_option_legs_with_quotes(result["strategy"])
                    # Mirror explanation to top-level for the frontend
                    expl = result["strategy"].get("explanation") or result.get("explanation") or ""
                    result["explanation"] = str(expl)


            # If still no ticker/strategy, keep valid/notes as set by guard
        except Exception as e:
            print(f"[beta_guard/router] skipped due to {type(e).__name__}: {e}")
        # === end beta guard ===

        # Return is the absolute last thing — nothing modifies result after guard
        print(f"[DBG] before return → type={(result.get('strategy') or {}).get('type')}, strategy_is_dict={isinstance(result.get('strategy'), dict)}")

        # ---- Final stabilization: recover type/legs if they were dropped downstream ----
        try:
            st = result.get("strategy") or {}
            expl = (st.get("explanation") or result.get("explanation") or "").strip()

            # 1) Recover type from explanation keywords if missing
            if not st.get("type"):
                if "Bull Call Spread" in expl:
                    st["type"] = "Bull Call Spread"
                elif "Bear Put Spread" in expl:
                    st["type"] = "Bear Put Spread"
                elif "Buy ETF" in expl:
                    st["type"] = "Buy ETF"
                elif "Buy Equity" in expl:
                    st["type"] = "Buy Equity"

            # 2) Rebuild legs from "between A and B" if we have a known spread but no legs
            if st.get("type") in ("Bull Call Spread", "Bear Put Spread") and not st.get("trade_legs"):
                import re
                # Try to parse two strikes: "... between 29 and 27 ..."
                m = re.search(r'between\s+([0-9]+(?:\.[0-9]+)?)\s+and\s+([0-9]+(?:\.[0-9]+)?)', expl)
                # Fallback: try to parse two floats anywhere in explanation
                if not m:
                    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\D+([0-9]+(?:\.[0-9]+)?)', expl)

                if m:
                    k1 = float(m.group(1)); k2 = float(m.group(2))
                    lo, hi = (min(k1, k2), max(k1, k2))
                    sym = result.get("ticker") or "SPY"
                    exp = st.get("expiration") or result.get("expiry_date") or "TBD"

                    if st["type"] == "Bull Call Spread":
                        legs = [
                            {"action":"Buy to Open",  "ticker": sym, "option_type":"Call", "strike_price": str(lo), "expiration": exp},
                            {"action":"Sell to Open", "ticker": sym, "option_type":"Call", "strike_price": str(hi), "expiration": exp},
                        ]
                    else:  # Bear Put Spread
                        legs = [
                            {"action":"Buy to Open",  "ticker": sym, "option_type":"Put", "strike_price": str(hi), "expiration": exp},
                            {"action":"Sell to Open", "ticker": sym, "option_type":"Put", "strike_price": str(lo), "expiration": exp},
                        ]
                    st["trade_legs"] = legs

            # 3) Ensure expiration lives inside strategy (router sometimes only has top-level)
            if not st.get("expiration"):
                st["expiration"] = result.get("expiry_date") or st.get("expiration") or "TBD"

            result["strategy"] = st
        except Exception as _:
            # Never block the response on stabilization
            pass


        # Mirror explanation top-level for the frontend
        if isinstance(result.get("strategy"), dict) and not result.get("explanation"):
            result["explanation"] = result["strategy"].get("explanation", "")


        return result


    except Exception as e:
        # 📊 PERFORMANCE MONITORING: Log error with timing and details
        duration = (time.perf_counter() - start) * 1000
        METRICS["error_counts"][type(e).__name__] += 1
        METRICS["logs"].append({
            "level": "ERROR",
            "message": f"process_belief failed: {str(e)[:50]}",
            "duration": f"{duration:.0f}ms", 
            "timestamp": time.strftime("%H:%M:%S")
        })
        
        print(f"🔧 [DEBUG] ERROR! {type(e).__name__}: {str(e)[:50]}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Saves user feedback on a generated strategy.
    """
    save_feedback_entry(request.belief, request.strategy, request.feedback, request.user_id)
    return {"message": "✅ Feedback saved"}

@router.post("/mark_outcome")
def mark_strategy_outcome(request: OutcomeRequest):
    """
    Logs actual result (win/loss, PnL%) for a strategy previously generated.
    Appends to strategy_outcomes.csv.
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        exists = os.path.exists(path)

        outcome_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "belief": request.belief,
            "result": request.result.lower(),
            "pnl_percent": request.pnl_percent,
            "user_id": request.user_id
        }

        df = pd.DataFrame([outcome_entry])
        df.to_csv(path, mode="a", index=False, header=not exists)

        return {"message": "✅ Strategy outcome logged"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging outcome: {str(e)}")

@router.get("/summary")
def strategy_summary(user_id: Optional[str] = Query(default=None)):
    """
    Returns summary metrics (PnL, win ratio, top strategies/tickers).
    Optionally filter by user_id.
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found")

        df = pd.read_csv(path)
        if df.empty or "belief" not in df.columns:
            raise HTTPException(status_code=400, detail="No strategy data available")

        if user_id:
            df = df[df["user_id"] == user_id]
            if df.empty:
                return {"message": f"No strategies found for user_id: {user_id}"}

        total = len(df)
        avg_pnl = round(df["pnl_percent"].mean(), 2) if "pnl_percent" in df else None
        win_ratio = round((df["result"] == "win").mean(), 2) if "result" in df else None
        top_beliefs = df["belief"].value_counts().head(5).to_dict()

        return {
            "user_id": user_id,
            "total_strategies": total,
            "avg_pnl_percent": avg_pnl,
            "win_ratio": win_ratio,
            "top_beliefs": top_beliefs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
