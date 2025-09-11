# backend/routes/paper_trading_router.py
# -----------------------------------------------------------------------------
# Paper & Live Trading Router (MarketPlayground)
# - Paper trading: portfolio, close (with optional qty + polling), leaderboard
# - Live trading (Alpaca): status probe, execute_live (stock/options), portfolio_live
# - Includes: payload normalization, safety rails, consistent no-store headers
# -----------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List, Tuple
from decimal import Decimal
import os
import time
import logging

# Local engine (paper trading)
from backend.paper_trading import paper_engine

# Live trading deps (Alpaca)
from backend.alpaca_orders import AlpacaExecutor
from backend.alpaca_client import get_account_info
from backend.alpaca_portfolio import get_live_positions

DEDUP_WINDOW = int(os.getenv("EXECUTION_SYMBOL_WINDOW_SECONDS", "30"))  # cooldown in seconds
_EXEC_CACHE: Dict[str, float] = {}  # cache of last order timestamps

def _dedupe_key(req: "TradeRequest") -> str:
    sd = req.strategy_data or {}
    t = (sd.get("type") or "").lower()
    side = (sd.get("side") or ("sell" if "sell" in t else "buy")).lower()
    sym = (sd.get("ticker") or sd.get("symbol") or "UNKNOWN").upper()
    qty = str(sd.get("quantity") or sd.get("qty") or 1)
    return f"{req.user_id}:{sym}:{side}:{qty}"  # unique key for dedupe


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# -----------------------------------------------------------------------------
# Config / Safety rails for LIVE trading
# -----------------------------------------------------------------------------
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "false").lower() in {"1", "true", "yes"}
LIVE_TRADING_WHITELIST = {
    u.strip() for u in os.getenv("LIVE_TRADING_WHITELIST", "").split(",") if u.strip()
}

def _to_float(x) -> float:
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x))
    except Exception:
        return 0.0

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class ClosePositionPayload(BaseModel):
    user_id: str
    position_id: str
    qty: Optional[str] = Field(default=None, description="If omitted → full close")

class TradeRequest(BaseModel):
    user_id: str = Field(..., description="App user placing the trade")
    strategy_data: Dict[str, Any] = Field(..., description="Normalized AI strategy payload")
    confirm_live: Optional[bool] = Field(default=False, description="Must be true to execute live")

# -----------------------------------------------------------------------------
# Order helpers (router-side)
# -----------------------------------------------------------------------------
def _is_options_intent(data: Dict[str, Any]) -> bool:
    """
    Heuristics to decide if incoming strategy_data describes an OPTIONS trade.
    Triggers on:
      - asset_class == 'options' (or 'option')
      - descriptor hints in 'description' (call/put/strike/expiration)
      - legs[] where leg contains option attributes (option_type etc.)
    """
    if not isinstance(data, dict):
        return False

    # Explicit asset class flag
    ac = (data.get("asset_class") or data.get("assetType") or "").strip().lower()
    if ac in {"option", "options"}:
        return True

    # Text hints
    desc = (data.get("description") or "").strip().lower()
    if any(k in desc for k in ("call", "put", "strike", "expiration", "expir")):
        return True

    # Legs that look like options
    legs = data.get("legs")
    if isinstance(legs, list) and legs:
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            lt = (leg.get("type") or leg.get("order_class") or "").lower()
            if "option" in lt or leg.get("option_type") is not None:
                return True

    return False

def _normalize_alpaca_equity_order(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Accepts various strategy payload shapes and returns an Alpaca-ready EQUITY order dict.
    Returns (order, error_message). If error_message is not None, validation failed.
    Note: this is intentionally narrow (equities only) to keep router concerns simple.
    """
    if not isinstance(data, dict):
        return None, "strategy_data must be an object"

    # Symbol hunting across common shapes
    symbol = (
        data.get("symbol")
        or data.get("ticker")
        or (data.get("underlying") or {}).get("symbol")
        or (
            data.get("order", {}).get("symbol")
            if isinstance(data.get("order"), dict) else None
        )
        or (
            data.get("strategy", {}).get("symbol")
            if isinstance(data.get("strategy"), dict) else None
        )
        or (
            data.get("strategy_data", {}).get("symbol")
            if isinstance(data.get("strategy_data"), dict) else None
        )
    )
    if not symbol or not isinstance(symbol, str):
        return None, "symbol not provided or invalid"

    side = (data.get("side") or data.get("action") or "").strip().lower()
    if side not in {"buy", "sell"}:
        return None, "side must be 'buy' or 'sell'"

    raw_qty = data.get("qty") or data.get("quantity") or data.get("shares")
    if raw_qty is None:
        return None, "qty is required"
    try:
        qty = int(str(raw_qty))
        if qty <= 0:
            return None, "qty must be > 0"
    except Exception:
        return None, "qty must be an integer"

    order_type = (data.get("type") or "market").strip().lower()
    tif = (data.get("time_in_force") or data.get("tif") or "day").strip().lower()

    order: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "side": side,
        "qty": str(qty),       # Alpaca accepts str or int; we send str to be safe at the router
        "type": order_type,
        "time_in_force": tif,
    }

    # Optional limit/stop
    if "limit_price" in data and data["limit_price"] is not None:
        order["limit_price"] = str(data["limit_price"])
    if "stop_price" in data and data["stop_price"] is not None:
        order["stop_price"] = str(data["stop_price"])

    return order, None

# -----------------------------------------------------------------------------
# Paper trading: Portfolio
# -----------------------------------------------------------------------------
@router.get("/portfolio/{user_id}")
def get_portfolio(user_id: str, force_refresh: bool = Query(True, description="Bypass any caches")):
    """Return latest paper portfolio snapshot with no-store headers."""
    try:
        portfolio = paper_engine.get_portfolio(user_id, force_refresh=force_refresh)
        return JSONResponse(
            content=portfolio,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.exception(f"Portfolio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Paper trading: Close position with optional partial qty + polling
# -----------------------------------------------------------------------------
@router.post("/close_position")
def close_position(payload: ClosePositionPayload):
    """
    Close a position (full or partial). We attempt to return a fresh portfolio.
    Behavior:
      - Calls engine.close_position(user_id, position_id, qty)
      - If engine finishes → 200 with realized P&L + fresh portfolio
      - If engine returns 'syncing' → poll up to 10×/500ms, else 202
    """
    try:
        user_id = payload.user_id
        position_id = payload.position_id
        qty = payload.qty

        # 1) Fire the close request
        result = paper_engine.close_position(user_id, position_id, qty)

        # Engine contract:
        # { status: 'closed'|'partially_closed'|'syncing'|'error', closed: {...}, portfolio: {...} }
        status = result.get("status")
        if status == "error":
            return JSONResponse(
                content=result,
                status_code=400,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        # 2) If we’re done (closed/partially_closed), return 200 immediately
        if status in {"closed", "partially_closed"}:
            return JSONResponse(
                content=result,
                status_code=200,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        # 3) If still syncing, poll the portfolio to surface a fresh snapshot
        if status == "syncing":
            for _ in range(10):  # 10 × 500ms = ~5s
                time.sleep(0.5)
                fresh = paper_engine.get_portfolio(user_id, force_refresh=True)

                # If the position is gone or qty decreased, consider it closed enough to show UI
                positions: List[Dict[str, Any]] = fresh.get("positions", [])
                still_there = next((p for p in positions if p.get("position_id") == position_id), None)
                if not still_there:
                    payload_out = {
                        "status": "closed",
                        "closed": result.get("closed", {}),
                        "portfolio": fresh,
                    }
                    return JSONResponse(
                        content=payload_out,
                        status_code=200,
                        headers={
                            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                            "Pragma": "no-cache",
                            "Expires": "0",
                        },
                    )

            # After polling, still syncing → tell FE to keep polling
            return JSONResponse(
                content={"status": "syncing"},
                status_code=202,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        # Fallback
        return JSONResponse(
            content=result,
            status_code=200,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        logger.exception(f"Close position error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Paper trading: Leaderboard
# -----------------------------------------------------------------------------
@router.get("/leaderboard")
def get_leaderboard():
    """Get performance leaderboard"""
    try:
        leaderboard = paper_engine.get_leaderboard()
        return JSONResponse(
            content=leaderboard,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# LIVE trading: status probe
# -----------------------------------------------------------------------------
@router.get("/live_status/{user_id}")
def live_status(user_id: str):
    """
    Returns whether live trading is enabled and whether the user is whitelisted.
    """
    enabled = ALLOW_LIVE_TRADING
    whitelisted = (not LIVE_TRADING_WHITELIST) or (user_id in LIVE_TRADING_WHITELIST)
    return JSONResponse(
        content={"enabled": enabled, "whitelisted": whitelisted},
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

# -----------------------------------------------------------------------------
# LIVE trading: execute order (stock OR options)
# -----------------------------------------------------------------------------
@router.post("/execute_live")
async def execute_live_trade(request: TradeRequest):
    """
    Execute a LIVE trade via Alpaca.

    Safety rails:
      - Requires ALLOW_LIVE_TRADING=true
      - If LIVE_TRADING_WHITELIST is set, user_id must be whitelisted
      - Requires request.confirm_live == true
    """
    if not ALLOW_LIVE_TRADING:
        raise HTTPException(status_code=403, detail="Live trading disabled by server config.")
    if LIVE_TRADING_WHITELIST and request.user_id not in LIVE_TRADING_WHITELIST:
        raise HTTPException(status_code=403, detail="User not permitted for live trading.")
    if not request.confirm_live:
        raise HTTPException(status_code=400, detail="Missing confirm_live=true for live execution.")
    k = _dedupe_key(request)  # unique key from user+order
    now = time.time()  # current timestamp
    last = _EXEC_CACHE.get(k, 0.0)  # last time this order key was seen
    if now - last < DEDUP_WINDOW:  # within cooldown window
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_or_too_soon",
                "retry_after": int(DEDUP_WINDOW - (now - last)),
                "key": k
            }
        )
    _EXEC_CACHE[k] = now  # record this order timestamp


    # Normalize equity order for the stock path; then branch cleanly by intent.
    normalized_equity, err = _normalize_alpaca_equity_order(request.strategy_data)
    is_options = _is_options_intent(request.strategy_data)

    if not is_options and err:
        logger.warning(f"execute_live validation error: {err} | payload={request.strategy_data}")
        raise HTTPException(status_code=400, detail=f"Invalid equity order: {err}")

    try:
        if is_options:
            # === OPTIONS PATH ===
            # Pass through raw strategy data, explicitly mark asset_class.
            executor_payload: Dict[str, Any] = {
                "asset_class": "options",
                "strategy_data": request.strategy_data,
                # convenience copies for executors with different envelopes:
                "order": request.strategy_data,
                "strategy": request.strategy_data,
            }

        else:
            # === STOCK PATH ===
            # Provide multiple envelopes + top-level keys (NO 'legs' here).
            assert normalized_equity is not None  # guarded above unless options path
            executor_payload = {
                # canonical normalized equity order:
                "strategy_data": normalized_equity,   # payload['strategy_data']['symbol']

                # common alt envelopes some executors expect:
                "order": normalized_equity,
                "strategy": normalized_equity,

                # top-level fallbacks (very common in older code):
                "symbol": normalized_equity["symbol"],
                "ticker": normalized_equity["symbol"],
                "side": normalized_equity["side"],
                "qty": int(normalized_equity["qty"]),
                "type": normalized_equity["type"],
                "time_in_force": normalized_equity["time_in_force"],

                # explicit class (lets executor short-circuit)
                "asset_class": "stock",
            }
            if "limit_price" in normalized_equity:
                executor_payload["limit_price"] = normalized_equity["limit_price"]
                executor_payload["order"]["limit_price"] = normalized_equity["limit_price"]
                executor_payload["strategy"]["limit_price"] = normalized_equity["limit_price"]
            if "stop_price" in normalized_equity:
                executor_payload["stop_price"] = normalized_equity["stop_price"]
                executor_payload["order"]["stop_price"] = normalized_equity["stop_price"]
                executor_payload["strategy"]["stop_price"] = normalized_equity["stop_price"]

        alpaca_executor = AlpacaExecutor()
        result = alpaca_executor.execute_order(executor_payload, request.user_id)

        content = {
            "status": result.get("status", "error"),
            "message": result.get("message", "Unknown"),
            "trading_mode": "live",
            "order_details": result,
            "normalized_order": normalized_equity,
            "sent_payload_debug": {
                "asset_class": executor_payload.get("asset_class"),
                "symbol": executor_payload.get("symbol"),
                "order_symbol": executor_payload.get("order", {}).get("symbol"),
                "strategy_symbol": executor_payload.get("strategy", {}).get("symbol"),
                "strategy_data_symbol": executor_payload.get("strategy_data", {}).get("symbol"),
            },
        }
        return JSONResponse(
            content=content,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        logger.exception(f"Live trade error: {e}")
        raise HTTPException(status_code=500, detail="Live trade failed")

# -----------------------------------------------------------------------------
# LIVE trading: portfolio
# -----------------------------------------------------------------------------
@router.get("/portfolio_live/{user_id}")
def get_live_portfolio(user_id: str):
    """
    Fetch LIVE Alpaca portfolio snapshot (account + positions).
    Harmonized with paper shape:
      {
        user_id, trading_mode,
        account{cash_balance,equity_value,buying_power,day_pnl},
        positions: [...],
        summary{total_positions}
      }
    """
    if not ALLOW_LIVE_TRADING:
        raise HTTPException(status_code=403, detail="Live trading disabled by server config.")

    try:
        account_info = get_account_info() or {}
        positions = get_live_positions() or []

        portfolio = {
            "user_id": user_id,
            "trading_mode": "live",
            "account": {
                "cash_balance": _to_float(account_info.get("cash", 0)),
                "equity_value": _to_float(account_info.get("equity", 0)),
                "buying_power": _to_float(account_info.get("buying_power", 0)),
                # Some Alpaca SDKs expose different keys for intraday PL
                "day_pnl": _to_float(
                    account_info.get("unrealized_intraday_pl")
                    or account_info.get("unrealized_pl")
                    or 0
                ),
            },
            "positions": positions,
            "summary": {"total_positions": len(positions)},
        }

        return JSONResponse(
            content=portfolio,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.exception(f"Live portfolio error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch live portfolio")
