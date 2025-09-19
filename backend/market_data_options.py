"""
backend/market_data_options.py
------------------------------

Purpose
=======
Centralized helpers to fetch options market data (chains, quotes, snapshots)
with a clean API your strategy/execute layers can call.

Design
======
- Provider-first: Tries **Alpaca Options Data** if credentials are present.
- Fallback: Returns empty/None gracefully if data isn’t available, so callers
  can decide what to do (e.g., use static heuristics, skip greeks, etc.).
- Zero new hard dependencies (uses stdlib + requests). If you later want
  yfinance/ibkr, you can plug them into the ProviderRegistry below.

Environment
===========
- ALPACA_API_KEY_ID
- ALPACA_API_SECRET_KEY
- ALPACA_DATA_BASE_URL (optional; defaults to https://data.alpaca.markets)
  NOTE: This is the **data** hostname, not the trading API host.

Usage
=====
from backend.market_data_options import (
    get_option_chain,
    get_option_quote,
    build_occ_symbol
)

chain = get_option_chain("AAPL", expiry="2025-09-20")
q = get_option_quote("AAPL", expiry="2025-09-20", strike=240, right="C")

"""

from __future__ import annotations
import os
import math
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import requests


# ---------------------------------------------------------------------------
# Utility: OCC option symbol builder (21-char format)
#   Root (1-6) + YYMMDD + C/P + Strike (8 digits = 5 int + 3 decimal, *1000)
#   Example: AAPL 2025-09-20 240.00 C -> "AAPL250920C00240000"
# ---------------------------------------------------------------------------
def build_occ_symbol(ticker: str, expiry: str, strike: float, right: str) -> str:
    """
    Build a 21-char OCC option symbol.
    - ticker: underlying root symbol (AAPL, SPY, etc.)
    - expiry: 'YYYY-MM-DD'
    - strike: e.g., 240 or 240.0
    - right: 'C' or 'P' (case-insensitive)

    Returns: e.g., 'AAPL250920C00240000'
    """
    root = (ticker or "").upper().strip()
    if not root:
        raise ValueError("ticker/root is required")

    try:
        y, m, d = map(int, expiry.split("-"))
        yy = y % 100
    except Exception as e:
        raise ValueError(f"Invalid expiry format (expected YYYY-MM-DD): {expiry}") from e

    right = (right or "").upper().strip()
    if right not in ("C", "P"):
        raise ValueError("right must be 'C' or 'P'")

    # Strike in OCC format: integer = price * 1000, zero-padded to 8
    strike_int = int(round(float(strike) * 1000))
    strike_str = f"{strike_int:08d}"

    return f"{root[:6]:<6}{yy:02d}{m:02d}{d:02d}{right}{strike_str}".replace(" ", "")


# ---------------------------------------------------------------------------
# Alpaca Options Data Provider
# Docs (subject to plan/entitlements):
#   Base:   https://data.alpaca.markets
#   Chain:  GET /v1beta1/options/chains?symbols=AAPL&expiration=2025-09-20
#   Quote:  GET /v1beta1/options/quotes/{occ_symbol}/latest
#   Snap:   GET /v1beta1/options/snapshots/{occ_symbol}
#   Bars:   GET /v1beta1/options/bars?symbols={occ_symbol}&timeframe=1Min&limit=...
#
# NOTE: Your account/tier must include options data access.
# ---------------------------------------------------------------------------
class AlpacaOptionsProvider:
    def __init__(self) -> None:
        self.base = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets").rstrip("/")
        self.key = os.getenv("ALPACA_API_KEY_ID", "")
        self.secret = os.getenv("ALPACA_API_SECRET_KEY", "")

    @property
    def ready(self) -> bool:
        return bool(self.key and self.secret)

    def _headers(self) -> Dict[str, str]:
        if not self.ready:
            raise RuntimeError("Alpaca credentials are missing")
        return {
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
            "Accept": "application/json",
        }

    def get_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        right: Optional[str] = None,  # 'call' or 'put'
        limit: int = 500,
    ) -> Dict[str, Any]:
        """
        Fetch an options chain for an underlying.
        Returns a dict with a 'contracts' list (normalized).
        """
        params = {"symbols": symbol.upper()}
        if expiry:
            params["expiration"] = expiry  # YYYY-MM-DD
        if right:
            params["type"] = right.lower()  # 'call'|'put'
        if limit:
            params["limit"] = str(limit)

        url = f"{self.base}/v1beta1/options/chains"
        r = requests.get(url, params=params, headers=self._headers(), timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca chain error {r.status_code}: {r.text}")

        data = r.json() or {}
        # Normalize a light-weight list
        contracts: List[Dict[str, Any]] = []
        for c in (data.get("chains") or []):
            try:
                contracts.append(
                    {
                        "symbol": c.get("symbol"),
                        "occ_symbol": c.get("occ_symbol"),
                        "expiration": c.get("expiration"),
                        "strike": float(c.get("strike")) if c.get("strike") is not None else None,
                        "right": c.get("type", "").upper()[:1],  # 'C' or 'P'
                    }
                )
            except Exception:
                continue

        return {"contracts": contracts, "raw": data}

    def get_quote_latest(self, occ_symbol: str) -> Dict[str, Any]:
        """
        Latest NBBO-like quote for an OCC option symbol.
        Returns normalized dict with bid/ask & timestamps.
        """
        url = f"{self.base}/v1beta1/options/quotes/{occ_symbol}/latest"
        r = requests.get(url, headers=self._headers(), timeout=10)
        if r.status_code == 404:
            return {}
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca quote error {r.status_code}: {r.text}")
        j = r.json() or {}
        q = (j.get("quote") or {})
        return {
            "occ_symbol": occ_symbol,
            "bid": q.get("bp"),
            "ask": q.get("ap"),
            "bid_size": q.get("bs"),
            "ask_size": q.get("as"),
            "timestamp": q.get("t"),
            "raw": j,
        }

    def get_snapshot(self, occ_symbol: str) -> Dict[str, Any]:
        """
        Snapshot includes latest trade/quote & more if entitled.
        """
        url = f"{self.base}/v1beta1/options/snapshots/{occ_symbol}"
        r = requests.get(url, headers=self._headers(), timeout=10)
        if r.status_code == 404:
            return {}
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca snapshot error {r.status_code}: {r.text}")
        return r.json() or {}


# ---------------------------------------------------------------------------
# Provider Registry (extensible)
# ---------------------------------------------------------------------------
class ProviderRegistry:
    """
    Simple registry that tries providers in order.
    Right now: Alpaca only. Add others later (IBKR, Polygon, yfinance, etc.).
    """
    def __init__(self) -> None:
        self.alpaca = AlpacaOptionsProvider()

    def best_available(self) -> Optional[str]:
        if self.alpaca.ready:
            return "alpaca"
        return None


REGISTRY = ProviderRegistry()


# ---------------------------------------------------------------------------
# Public functions your code can call (clean API)
# ---------------------------------------------------------------------------
def get_option_chain(
    symbol: str,
    expiry: Optional[str] = None,
    right: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Return an options chain dict:
      { 'contracts': [ {occ_symbol, expiration, strike, right}, ... ], 'source': 'alpaca'|'none' }
    """
    src = REGISTRY.best_available()
    if src == "alpaca":
        try:
            out = REGISTRY.alpaca.get_chain(symbol, expiry=expiry, right=right, limit=limit)
            out["source"] = "alpaca"
            return out
        except Exception as e:
            return {"contracts": [], "source": "alpaca", "error": str(e)}
    # Fallback (no provider available)
    return {"contracts": [], "source": "none"}


def get_option_quote(
    symbol: str,
    expiry: str,
    strike: float,
    right: str,
    use_snapshot: bool = False,
) -> Dict[str, Any]:
    """
    Return latest quote or snapshot for the requested contract.
    - Builds OCC symbol internally from (symbol, expiry, strike, right).
    - If provider missing/unavailable, returns {} with 'source':'none'
    """
    occ = build_occ_symbol(symbol, expiry, strike, right)
    src = REGISTRY.best_available()
    if src == "alpaca":
        try:
            if use_snapshot:
                j = REGISTRY.alpaca.get_snapshot(occ)
                return {"source": "alpaca", "occ_symbol": occ, "snapshot": j}
            else:
                q = REGISTRY.alpaca.get_quote_latest(occ)
                q["source"] = "alpaca"
                return q
        except Exception as e:
            return {"source": "alpaca", "occ_symbol": occ, "error": str(e)}
    return {"source": "none", "occ_symbol": occ}


# ---------------------------------------------------------------------------
# Quick self-test when run directly (safe; no exceptions on missing creds)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    print("[self-test] provider:", REGISTRY.best_available())
    try:
        ch = get_option_chain("AAPL", expiry="2025-09-20", right="call", limit=10)
        print("[chain] source:", ch.get("source"), "n_contracts:", len(ch.get("contracts", [])))
    except Exception as e:
        print("[chain] error:", e)

    try:
        q = get_option_quote("AAPL", "2025-09-20", 240, "C")
        print("[quote] source:", q.get("source"), "keys:", list(q.keys()))
    except Exception as e:
        print("[quote] error:", e)
