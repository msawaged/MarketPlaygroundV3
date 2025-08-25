# backend/utils/symbol_universe.py
import os, requests, threading
from typing import Optional, Set

_ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
_ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY", "")
_BASE = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
_HEADERS = {"APCA-API-KEY-ID": _ALPACA_KEY, "APCA-API-SECRET-KEY": _ALPACA_SECRET}

# 🟢 Debug: show which Alpaca key tail + env mode we’re using at import time
_env_mode = "paper" if "paper-api.alpaca.markets" in (_BASE or "") else "live"
print(
    f"[SYMBOL_UNIVERSE] Using Alpaca key tail: "
    f"{(_ALPACA_KEY[-4:] if _ALPACA_KEY else 'NONE')} "
    f"(env={_env_mode}, base={_BASE})"
)

# Thread-safe lazy loader
_symbols_lock = threading.Lock()
_SYMBOLS: Optional[Set[str]] = None

# --- Step B hardening: normalization + guards ---
ALLOWED_SINGLE_LETTER: Set[str] = set()  # add any valid single-letter tickers if Alpaca supports them


def normalize_ticker(t: str) -> str:
    """Normalize incoming ticker strings consistently."""
    return (t or "").strip().upper()


def _is_clean_symbol(t: str) -> bool:
    """
    Quick hygiene gate:
    - non-empty
    - strictly alphanumeric (blocks 'BRK.B', 'SPY!' etc.)
      (If you need dots/dashes later, add a mapper upstream before calling this.)
    - disallow single-letter unless whitelisted
    """
    if not t:
        return False
    if any(not c.isalnum() for c in t):
        return False
    if len(t) == 1 and t not in ALLOWED_SINGLE_LETTER:
        return False
    return True


def _fetch_assets(status="active", asset_class="us_equity", exch=None):
    """
    Fetch asset list from Alpaca REST API using the configured _BASE.
    """
    params = {"status": status, "asset_class": asset_class}
    if exch:
        params["exchange"] = exch

    url = f"{_BASE}/v2/assets"
    print(f"[SYMBOL_UNIVERSE] Fetching assets from {url} …")  # 🔍 debug print

    r = requests.get(url, headers=_HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()  # list of assets


def load_symbol_universe() -> Set[str]:
    """
    Load active tradable symbols from Alpaca (US equities/ETFs).
    Returns uppercase set; cached for the process lifetime.
    """
    global _SYMBOLS
    with _symbols_lock:
        if _SYMBOLS is not None:
            return _SYMBOLS

        symbols: Set[str] = set()
        try:
            assets = _fetch_assets(status="active", asset_class="us_equity")
            for a in assets:
                sym = normalize_ticker(a.get("symbol", ""))
                tradable = a.get("tradable", False)
                if tradable and _is_clean_symbol(sym):
                    symbols.add(sym)
        except Exception as e:
            print(f"[SYMBOL_UNIVERSE] Failed to load from Alpaca: {e}")

        # Minimal safety fallback so app doesn’t crash if network fails
        if not symbols:
            symbols.update({"AAPL", "TSLA", "SPY", "QQQ", "USO", "TLT"})

        _SYMBOLS = symbols
        print(f"[SYMBOL_UNIVERSE] Loaded {len(_SYMBOLS)} symbols.")
        return _SYMBOLS


def is_tradable_symbol(sym: str) -> bool:
    """
    Public gate used by pricing and parsers.
    - Normalize
    - Hygiene check (alnum, length)
    - Membership in loaded Alpaca universe
    """
    t = normalize_ticker(sym)
    if not _is_clean_symbol(t):
        return False
    return t in load_symbol_universe()
