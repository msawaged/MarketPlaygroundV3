# ============================================================
# backend/data_sources/alpaca_news.py
# ============================================================
# PURPOSE:
#   - Thin wrapper around Alpaca News API (v1beta1).
#   - Used by Creative Mapping to discover tickers from news.
#
# DESIGN:
#   - Safe: returns [] if no API keys are provided.
#   - Pure functions, no side effects.
#   - JSON responses normalized into consistent dicts.
#
# ENV VARS REQUIRED:
#   - ALPACA_API_KEY
#   - ALPACA_API_SECRET
# OPTIONAL:
#   - ALPACA_BASE_URL (defaults to https://data.alpaca.markets)
#
# FUNCTIONS:
#   - search_news(query, since_days=14, limit=50, include_content=False)
#   - get_trending_symbols(limit=10)
#
# USAGE:
#   from backend.data_sources.alpaca_news import search_news, get_trending_symbols
#   results = search_news("Taylor Swift")
#   hot = get_trending_symbols(5)
# ============================================================

from __future__ import annotations
from typing import Dict, List
import os
import datetime as dt
import requests

# ------------------------------------------------------------
# CONFIG: Load API keys + base URL
# ------------------------------------------------------------
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://data.alpaca.markets")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")


# ------------------------------------------------------------
# INTERNAL: headers for Alpaca REST calls
# ------------------------------------------------------------
def _headers() -> Dict[str, str]:
    return {
        "Apca-Api-Key-Id": ALPACA_API_KEY or "",
        "Apca-Api-Secret-Key": ALPACA_API_SECRET or "",
    }


# ------------------------------------------------------------
# MAIN: search_news
# ------------------------------------------------------------
def search_news(
    query: str,
    since_days: int = 14,
    limit: int = 50,
    include_content: bool = False,
) -> List[Dict]:
    """
    Query Alpaca News API for articles mentioning query terms.

    Parameters:
        query (str): Search string (company, event, person, etc).
        since_days (int): How far back to search (default 14 days).
        limit (int): Max results (default 50).
        include_content (bool): Include full article body if available.

    Returns:
        List[Dict]: Normalized list of articles with fields:
            - id, headline, summary, symbols, source, created_at, url, author
    """

    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        # No API keys → safe fallback
        return []

    # Build time window
    start = (dt.datetime.utcnow() - dt.timedelta(days=since_days)).isoformat() + "Z"
    params = {
        "search": query,
        "start": start,
        "limit": limit,
        "include_content": str(include_content).lower(),
    }

    url = f"{ALPACA_BASE_URL}/v1beta1/news"
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("news", []):
        results.append({
            "id": str(item.get("id")),
            "headline": item.get("headline", "") or "",
            "summary": item.get("summary", "") or "",
            "symbols": item.get("symbols", []) or [],
            "source": item.get("source", "") or "",
            "created_at": item.get("created_at", "") or "",
            "url": item.get("url", "") or "",
            "author": item.get("author", None),
        })
    return results


# ------------------------------------------------------------
# EXTRA: get_trending_symbols
# ------------------------------------------------------------
def get_trending_symbols(limit: int = 10) -> List[str]:
    """
    Return most-mentioned symbols in last 24 hours of Alpaca news.

    Parameters:
        limit (int): Max number of trending tickers to return.

    Returns:
        List[str]: Top N ticker symbols (uppercased).
    """

    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        return []

    url = f"{ALPACA_BASE_URL}/v1beta1/news"
    params = {
        "limit": 200,
        "start": (dt.datetime.utcnow() - dt.timedelta(hours=24)).isoformat() + "Z",
    }

    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        from collections import Counter
        counts = Counter()
        for item in data.get("news", []):
            for sym in item.get("symbols", []) or []:
                su = (sym or "").upper()
                if _is_valid_equity_symbol(su):
                    counts[su] += 1
        return [s for s, _ in counts.most_common(limit)]
    except Exception:
        return []


# ------------------------------------------------------------
# HELPER: validate equity tickers
# ------------------------------------------------------------
def _is_valid_equity_symbol(sym: str) -> bool:
    if not sym:
        return False
    s = sym.upper()
    if len(s) > 5 and "." not in s:  # allow BRK.B style
        return False
    if not all(c.isalnum() or c == "." for c in s):
        return False
    blacklist = {"USD", "EUR", "GBP", "JPY", "BTC", "ETH", "VIX", "DXY", "WTI", "BRENT"}
    return s not in blacklist
