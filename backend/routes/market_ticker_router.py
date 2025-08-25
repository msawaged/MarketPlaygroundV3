# backend/routes/market_ticker_router.py
import os, requests, time
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query

ROUTER = APIRouter(prefix="/ticker", tags=["ticker"])

ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY", "")
DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
TRADE_BASE = os.getenv("ALPACA_TRADING_BASE", "https://paper-api.alpaca.markets")

HDRS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

def _get(url: str, params: Dict[str, Any] | None = None, timeout: int = 20) -> Dict[str, Any]:
    r = requests.get(url, headers=HDRS, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _safe_float(x):
    try:
        return None if x is None else float(x)
    except Exception:
        return None

def _single_symbol_prices(sym: str) -> Dict[str, Any]:
    """
    Robust per-symbol fetch that should work across most Alpaca Data plans:
      - /v2/stocks/{sym}/bars/latest  -> last trade/close (price)
      - /v2/stocks/{sym}/bars?timeframe=1Day&limit=2 -> prevClose
      - /v2/stocks/{sym}/quotes/latest -> mid price fallback if needed
    """
    sym = sym.upper()
    out = {"symbol": sym, "price": None, "prevClose": None}

    # latest bar (price)
    try:
        lb = _get(f"{DATA_BASE}/v2/stocks/{sym}/bars/latest")
        bar = (lb or {}).get("bar") or {}
        out["price"] = _safe_float(bar.get("c"))
    except Exception:
        pass

    # daily bars (prevClose)
    try:
        hist = _get(f"{DATA_BASE}/v2/stocks/{sym}/bars", {"timeframe": "1Day", "limit": 2})
        bars = hist.get("bars") or []
        if len(bars) >= 2:
            out["prevClose"] = _safe_float(bars[-2].get("c"))
        elif len(bars) == 1:
            out["prevClose"] = _safe_float(bars[0].get("c"))
    except Exception:
        pass

    # if price still None -> mid of latest quote
    if out["price"] is None:
        try:
            lq = _get(f"{DATA_BASE}/v2/stocks/{sym}/quotes/latest")
            q = (lq or {}).get("quote") or {}
            bp, ap = _safe_float(q.get("bp")), _safe_float(q.get("ap"))
            if bp is not None and ap is not None:
                out["price"] = round((bp + ap) / 2.0, 4)
        except Exception:
            pass

    return out

@ROUTER.get("/prices")
def get_prices(
    tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,TSLA,MSFT"),
    debug: bool = Query(False),
):
    symbols = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    if not symbols:
        return []

    results: List[Dict[str, Any]] = []
    debug_msgs: List[str] = []

    # Try batch snapshots first (best-effort). If plan blocks it, we fall back.
    try:
        batch = _get(f"{DATA_BASE}/v2/stocks/snapshots", {"symbols": ",".join(symbols)})
        snaps = batch.get("snapshots") or {}
    except Exception as e:
        snaps = {}
        if debug:
            debug_msgs.append(f"batch_error: {type(e).__name__}: {e}")

    for s in symbols:
        price = None
        prev = None

        # Use snapshot if present
        snap = snaps.get(s) if isinstance(snaps, dict) else None
        if isinstance(snap, dict):
            lt = (snap.get("latestTrade") or {}).get("p")
            prev = (snap.get("prevDailyBar") or {}).get("c")
            if lt is None:
                q = snap.get("latestQuote") or {}
                bid, ask = q.get("bp"), q.get("ap")
                if bid is not None and ask is not None:
                    lt = round((float(bid) + float(ask)) / 2.0, 4)
            price = _safe_float(lt)
            prev = _safe_float(prev)

        # If snapshot missing/empty, get robust per-symbol data
        if price is None and prev is None:
            robust = _single_symbol_prices(s)
            price = robust.get("price")
            prev = robust.get("prevClose")

        if price is not None or prev is not None:
            change = None if (price is None or prev is None) else (price - prev)
            change_pct = None if (price is None or prev in (None, 0)) else (change / prev * 100.0)
            results.append({
                "symbol": s,
                "price": price,
                "prevClose": prev,
                "change": change,
                "changePercent": change_pct
            })

    if not results and debug:
        return [{"_debug": "no data for all symbols"},
                {"_env": {
                    "ALPACA_KEY_set": bool(ALPACA_KEY),
                    "ALPACA_SECRET_set": bool(ALPACA_SECRET),
                    "DATA_BASE": DATA_BASE
                }},
                {"_notes": debug_msgs or ["check API keys / plan; try per-symbol curl directly"]}]

    return results

# ---- Fuzzy search (unchanged): /v2/assets, cached in memory ----

_ASSETS_CACHE_TS = 0
_ASSETS_TTL = 60 * 60 * 12  # 12h
_ASSETS_ROWS: List[Dict[str, Any]] = []

def _load_assets() -> List[Dict[str, Any]]:
    global _ASSETS_CACHE_TS, _ASSETS_ROWS
    now = int(time.time())
    if now - _ASSETS_CACHE_TS < _ASSETS_TTL and _ASSETS_ROWS:
        return _ASSETS_ROWS
    rows = _get(f"{TRADE_BASE}/v2/assets")
    rows = [r for r in rows if (r.get("status") == "active")]
    _ASSETS_ROWS = rows
    _ASSETS_CACHE_TS = now
    return rows

@ROUTER.get("/search")
def search_tickers(query: str = Query(..., min_length=1), limit: int = 10):
    q = query.strip().lower()
    assets = _load_assets()
    sym_starts, sym_contains, name_contains = [], [], []
    for a in assets:
        sym = (a.get("symbol") or "").upper()
        name = (a.get("name") or "")
        s_low, n_low = sym.lower(), name.lower()
        if s_low.startswith(q): sym_starts.append(sym)
        elif q in s_low: sym_contains.append(sym)
        elif q in n_low: name_contains.append(sym)
    ordered = []
    for arr in (sym_starts, sym_contains, name_contains):
        for s in arr:
            if s not in ordered:
                ordered.append(s)
            if len(ordered) >= limit:
                break
        if len(ordered) >= limit:
            break
    return ordered
