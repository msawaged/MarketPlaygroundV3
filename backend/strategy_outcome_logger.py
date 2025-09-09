# backend/strategy_outcome_logger.py

"""
Logs and tracks the performance of executed strategies (win/loss/PnL).
Includes summary statistics for dashboards or leaderboards.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter

# 📍 CSV log file path
OUTCOME_LOG = os.path.join(os.path.dirname(__file__), "strategy_outcomes.csv")


def _coerce_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _strategy_type(s) -> str:
    """Return a readable strategy type; safe when s is None/not a dict."""
    return s.get("type", "unknown") if isinstance(s, dict) else "BLOCKED"


def _strategy_risk(s) -> str:
    return s.get("risk_level", "unknown") if isinstance(s, dict) else "unknown"


def log_strategy_outcome(strategy: Optional[dict],
                         belief: str,
                         ticker: str,
                         pnl_percent: float,
                         result: str,
                         notes: str = "",
                         user_id: Optional[str] = None,
                         holding_period_days: Optional[int] = None):
    """
    Logs the outcome of a strategy after execution or simulation.
    Safe when `strategy` is None (e.g., blocked/misaligned).

    Args:
        strategy (dict|None): Strategy returned by the AI engine, or None if blocked
        belief (str): Original belief
        ticker (str): Ticker traded
        pnl_percent (float): Return percentage
        result (str): 'win', 'loss', 'neutral', 'pending', or 'blocked'
        notes (str): Optional annotation
        user_id (str): Optional user identifier
        holding_period_days (int): Days between belief and outcome evaluation
    """
    # If strategy is None, treat as blocked unless caller specified otherwise
    safe_result = result or ("blocked" if strategy is None else "pending")

    log_entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": (user_id or "anonymous"),
        "belief": str(belief or ""),
        "strategy": _strategy_type(strategy),
        "ticker": str(ticker or ""),
        "pnl_percent": round(_coerce_float(pnl_percent, 0.0), 2),
        "result": safe_result,
        "risk": _strategy_risk(strategy),
        "holding_period_days": holding_period_days if holding_period_days is not None else "",
        "notes": notes or "",
    }

    file_exists = os.path.isfile(OUTCOME_LOG)
    with open(OUTCOME_LOG, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_entry)
        print(f"✅ Strategy outcome logged:\n{log_entry}")


def log_strategy_result(result: Dict) -> None:
    """
    Convenience wrapper that logs directly from the engine `result` dict.
    Handles strategy=None (blocked) without crashing.

    Expected keys (best-effort): belief, user_id, ticker, strategy, notes/reason.
    """
    try:
        belief = str(result.get("belief", "") or result.get("input_belief", "") or "")
        user_id = result.get("user_id") or "anonymous"
        ticker = str(result.get("ticker") or "")
        strategy = result.get("strategy")  # may be None
        notes = result.get("notes") or result.get("reason") or "Strategy generated - awaiting execution/feedback"

        # If strategy is None → blocked; else pending by default
        status = "blocked" if not isinstance(strategy, dict) else "pending"

        log_strategy_outcome(
            strategy=strategy,
            belief=belief,
            ticker=ticker,
            pnl_percent=0.0,
            result=status,
            notes=notes,
            user_id=user_id,
            holding_period_days=None,
        )
    except Exception as e:
        print(f"⚠️ Failed to log strategy outcome safely (result wrapper): {e}")


def get_all_outcomes() -> List[Dict]:
    """
    Returns all strategy outcomes from the log.

    Returns:
        List[Dict]: Full list of strategy outcome records.
    """
    if not os.path.exists(OUTCOME_LOG):
        return []
    with open(OUTCOME_LOG, mode="r", newline="") as f:
        return list(csv.DictReader(f))


def get_summary_stats(filter_ticker: Optional[str] = None,
                      filter_user: Optional[str] = None) -> Dict:
    """
    Computes summary statistics over all logged outcomes.

    Args:
        filter_ticker (str): If set, limits results to a specific ticker
        filter_user (str): If set, limits results to a specific user_id

    Returns:
        Dict: Summary stats (totals, averages, win/loss ratio, top strategies)
    """
    entries = get_all_outcomes()
    if filter_ticker:
        entries = [e for e in entries if e["ticker"] == filter_ticker]
    if filter_user:
        entries = [e for e in entries if e["user_id"] == filter_user]

    total = len(entries)
    if total == 0:
        return {
            "total": 0,
            "avg_pnl": 0,
            "win_rate": "0%",
            "most_common_ticker": None,
            "most_common_strategy": None
        }

    wins = sum(1 for e in entries if e["result"] == "win")
    avg_pnl = sum(_coerce_float(e["pnl_percent"], 0.0) for e in entries) / total
    most_ticker = Counter(e["ticker"] for e in entries).most_common(1)[0][0]
    most_strategy = Counter(e["strategy"] for e in entries).most_common(1)[0][0]

    return {
        "total": total,
        "avg_pnl": round(avg_pnl, 2),
        "win_rate": f"{round((wins / total) * 100, 1)}%",
        "most_common_ticker": most_ticker,
        "most_common_strategy": most_strategy
    }


# 🧪 Run directly to simulate a test log
if __name__ == "__main__":
    test_strategy = {
        "type": "bull call spread",
        "risk_level": "high",
        "description": "Buy AAPL 200c / Sell AAPL 215c",
        "suggested_allocation": "20%",
        "explanation": "Bullish strategy"
    }

    log_strategy_outcome(
        strategy=test_strategy,
        belief="I think AAPL will rise after earnings",
        ticker="AAPL",
        pnl_percent=18.25,
        result="win",
        notes="simulated test",
        user_id="murad34",
        holding_period_days=7
    )

    print("\n📊 Summary Stats:", get_summary_stats())
