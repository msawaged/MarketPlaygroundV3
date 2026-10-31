"""
Market data for v4, from Alpaca.

- asset_info(): is the symbol real, active and tradable on Alpaca?
- daily_closes(): daily close history (cached in-process; one fetch per symbol
  covers both live pricing and historical backfill/grading).
- price_on(): close on or before a date (or the latest trade for "today").
- features(): simple, as-of-date market features for the neural network
  (momentum, volatility, relative strength vs SPY). Only data up to the
  as-of date is used, so backfilled examples never see the future.

Env:
  ALPACA_API_KEY / ALPACA_SECRET_KEY
  ALPACA_BASE_URL      (trading API, default paper)
  ALPACA_DATA_BASE     (default https://data.alpaca.markets)
  ALPACA_DATA_FEED     (iex | sip, default iex — works on the free plan)
"""
from __future__ import annotations

import re

import bisect
import math
import os
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

_session = requests.Session()
_lock = threading.RLock()
_bars_cache: dict[str, tuple[list[str], list[float]]] = {}
_asset_cache: dict[str, Optional[dict]] = {}
_bars_at: dict[str, float] = {}
BARS_TTL = float(os.getenv("MP_BARS_TTL_SECONDS", str(6 * 3600)))
HISTORY_YEARS = int(os.getenv("MP_HISTORY_YEARS", "5"))


class MarketDataError(RuntimeError):
    pass


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY", ""),
        "accept": "application/json",
    }


def _trading_base() -> str:
    return os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")


def _data_base() -> str:
    return os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets").rstrip("/")


NY = None
try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    pass


def now_ny() -> datetime:
    return datetime.now(NY) if NY else datetime.now(timezone.utc) - timedelta(hours=5)


def today() -> date:
    """The trading calendar's date (New York). UTC rolled over at 6pm Denver and stamped
    evening beliefs with tomorrow's date."""
    return now_ny().date()


def _session_open_dt(d: str) -> datetime:
    """9:30am New York on trading date d (YYYY-MM-DD), as an aware datetime."""
    y, m, dd = (int(x) for x in d.split("-"))
    return datetime(y, m, dd, 9, 30, tzinfo=NY) if NY else datetime(y, m, dd, 14, 30, tzinfo=timezone.utc)


_clock_cache: dict = {"at": 0.0, "v": None}


def _fallback_clock() -> dict:
    """Weekdays 9:30-16:00 New York (ignores holidays) when Alpaca's clock can't be reached."""
    n = now_ny()
    is_open = n.weekday() < 5 and (n.hour, n.minute) >= (9, 30) and n.hour < 16
    d = n.date()
    if n.weekday() >= 5 or (n.hour, n.minute) >= (9, 30):
        d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return {"is_open": is_open, "next_open": _session_open_dt(d.isoformat()).isoformat(), "next_close": None, "source": "fallback"}


def clock() -> dict:
    """{'is_open', 'next_open', 'next_close'} from Alpaca's market clock (handles holidays), cached 60s."""
    import time as _t
    with _lock:
        if _clock_cache["v"] and _t.time() - _clock_cache["at"] < 60:
            return _clock_cache["v"]
    v = None
    try:
        r = _session.get(f"{_trading_base()}/v2/clock", headers=_headers(), timeout=6)
        if r.status_code == 200:
            j = r.json()
            v = {"is_open": bool(j.get("is_open")), "next_open": j.get("next_open"), "next_close": j.get("next_close"), "source": "alpaca"}
    except requests.RequestException:
        pass
    v = v or _fallback_clock()
    with _lock:
        _clock_cache.update(at=_t.time(), v=v)
    return v


def is_open() -> bool:
    return bool(clock().get("is_open"))


def session_open_after(symbol: str, after: datetime) -> Optional[tuple[str, float]]:
    """(trading date, opening price) of the first regular session that opens at or after `after`
    (aware datetime). None if that session hasn't opened yet. Used to fill orders placed while the
    market was closed at the price they would really have gotten."""
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    start = (after.astimezone(NY).date() if NY else after.date()) - timedelta(days=1)
    try:
        r = _session.get(f"{_data_base()}/v2/stocks/{symbol.upper()}/bars", headers=_headers(), params={
            "timeframe": "1Day", "start": start.isoformat(), "adjustment": "raw",
            "feed": os.getenv("ALPACA_DATA_FEED", "iex"), "limit": 30}, timeout=10)
    except requests.RequestException as e:
        raise MarketDataError(f"bars fetch failed for {symbol}: {e}") from e
    if r.status_code != 200:
        raise MarketDataError(f"bars {symbol}: HTTP {r.status_code}")
    for b in r.json().get("bars") or []:
        d = b["t"][:10]
        if _session_open_dt(d) >= after and _session_open_dt(d) <= datetime.now(timezone.utc):
            return d, float(b["o"])
    return None


def asset_info(symbol: str) -> Optional[dict]:
    """Return {'symbol','name','tradable','is_etf',...} or None if not a usable US equity."""
    symbol = symbol.upper().strip()
    with _lock:
        if symbol in _asset_cache:
            return _asset_cache[symbol]
    try:
        r = _session.get(f"{_trading_base()}/v2/assets/{symbol}", headers=_headers(), timeout=8)
    except requests.RequestException as e:
        raise MarketDataError(f"asset lookup failed for {symbol}: {e}") from e
    info: Optional[dict] = None
    if r.status_code == 200:
        a = r.json()
        if a.get("class") == "us_equity" and a.get("status") == "active" and a.get("tradable"):
            name = a.get("name") or ""
            info = {
                "symbol": a.get("symbol", symbol),
                "name": name,
                "exchange": a.get("exchange"),
                "tradable": True,
                "fractionable": bool(a.get("fractionable")),
                "is_etf": _looks_like_etf(name),
            }
    elif r.status_code not in (404, 422):
        raise MarketDataError(f"asset lookup {symbol}: HTTP {r.status_code}")
    with _lock:
        _asset_cache[symbol] = info
    return info


def _looks_like_etf(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in (" etf", "trust", "fund", "ishares", "spdr", "vaneck", "invesco", "proshares"))


def daily_closes(symbol: str) -> tuple[list[str], list[float]]:
    """(dates ascending as 'YYYY-MM-DD', closes). Cached per process."""
    symbol = symbol.upper()
    import time as _t
    with _lock:
        if symbol in _bars_cache and _t.time() - _bars_at.get(symbol, 0) < BARS_TTL:
            return _bars_cache[symbol]
    start = (today() - timedelta(days=365 * HISTORY_YEARS + 30)).isoformat()
    params = {
        "timeframe": "1Day",
        "start": start,
        "adjustment": "all",
        "feed": os.getenv("ALPACA_DATA_FEED", "iex"),
        "limit": 10000,
    }
    dates: list[str] = []
    closes: list[float] = []
    page = None
    for _ in range(20):
        if page:
            params["page_token"] = page
        try:
            r = _session.get(f"{_data_base()}/v2/stocks/{symbol}/bars", headers=_headers(), params=params, timeout=15)
        except requests.RequestException as e:
            raise MarketDataError(f"bars fetch failed for {symbol}: {e}") from e
        if r.status_code != 200:
            raise MarketDataError(f"bars {symbol}: HTTP {r.status_code} {r.text[:120]}")
        data = r.json()
        for b in data.get("bars") or []:
            dates.append(b["t"][:10])
            closes.append(float(b["c"]))
        page = data.get("next_page_token")
        if not page:
            break
    with _lock:
        _bars_cache[symbol] = (dates, closes)
        _bars_at[symbol] = _t.time()
    return dates, closes


def latest_price(symbol: str) -> float:
    try:
        r = _session.get(
            f"{_data_base()}/v2/stocks/{symbol.upper()}/trades/latest",
            headers=_headers(),
            params={"feed": os.getenv("ALPACA_DATA_FEED", "iex")},
            timeout=8,
        )
        if r.status_code == 200:
            p = (r.json().get("trade") or {}).get("p")
            if p:
                return float(p)
    except requests.RequestException:
        pass
    dates, closes = daily_closes(symbol)
    if not closes:
        raise MarketDataError(f"no price for {symbol}")
    return closes[-1]


def _index_on_or_before(dates: list[str], d: str) -> int:
    return bisect.bisect_right(dates, d) - 1


def price_on(symbol: str, d: Optional[date] = None) -> tuple[str, float]:
    """(date_used, price). d=None or today → latest live price."""
    if d is None or d >= today():
        return today().isoformat(), latest_price(symbol)
    dates, closes = daily_closes(symbol)
    i = _index_on_or_before(dates, d.isoformat())
    if i < 0:
        raise MarketDataError(f"no history for {symbol} on/before {d}")
    return dates[i], closes[i]


def close_on_or_after(symbol: str, d: date) -> Optional[tuple[str, float]]:
    dates, closes = daily_closes(symbol)
    i = bisect.bisect_left(dates, d.isoformat())
    if i >= len(dates):
        return None
    return dates[i], closes[i]


def _ret(closes: list[float], i: int, lag: int) -> float:
    if i - lag < 0 or closes[i - lag] <= 0:
        return 0.0
    return closes[i] / closes[i - lag] - 1.0


def realized_vol(closes: list[float], i: int, window: int = 20) -> float:
    lo = max(1, i - window + 1)
    rets = [math.log(closes[k] / closes[k - 1]) for k in range(lo, i + 1) if closes[k - 1] > 0]
    if len(rets) < 5:
        return 0.35
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return max(0.05, min(2.5, math.sqrt(var) * math.sqrt(252)))


def features(symbol: str, as_of: Optional[date] = None) -> dict:
    """Market features using only data up to as_of."""
    d = (as_of or today()).isoformat()
    dates, closes = daily_closes(symbol)
    i = _index_on_or_before(dates, d)
    if i < 20:
        raise MarketDataError(f"not enough history for {symbol} as of {d}")
    sdates, scloses = daily_closes("SPY")
    j = _index_on_or_before(sdates, d)
    hi252 = max(closes[max(0, i - 251): i + 1])
    vol60 = realized_vol(closes, i, 60)
    return {
        "mom20": _ret(closes, i, 20),
        "mom60": _ret(closes, i, 60),
        "mom250": _ret(closes, i, 250),
        "vol20": realized_vol(closes, i, 20),
        "vol60": vol60,
        "rs60": _ret(closes, i, 60) - (_ret(scloses, j, 60) if j >= 60 else 0.0),
        "dist_high": closes[i] / hi252 - 1.0 if hi252 > 0 else 0.0,
        "log_price": math.log(max(closes[i], 0.01)),
        "history_days": min(i, 1000),
    }


def clear_cache() -> None:
    with _lock:
        _bars_cache.clear()
        _asset_cache.clear()
        _clock_cache.update(at=0.0, v=None)


_news_cache: dict = {"at": 0.0, "items": []}


news_error = {"v": ""}


def headlines(limit: int = 6) -> list[dict]:
    """Latest market headlines from Alpaca's news feed, cached 20 minutes. [] when unavailable."""
    import time
    with _lock:
        if time.time() - _news_cache["at"] < 1200 and _news_cache["items"]:
            return _news_cache["items"][:limit]
    try:
        r = _session.get(f"{_data_base()}/v1beta1/news", headers=_headers(),
                         params={"limit": 50, "sort": "desc", "include_content": "false"}, timeout=8)
        if r.status_code != 200:
            news_error["v"] = f"news HTTP {r.status_code}: {r.text[:120]}"
            return []
        raw = r.json().get("news", [])
        news_error["v"] = "" if raw else "news source returned 0 articles"
    except Exception as e:
        news_error["v"] = f"news: {type(e).__name__}: {str(e)[:120]}"
        return []
    items, seen = [], set()
    for n in raw:
        h = (n.get("headline") or "").strip()
        key = h.lower()[:60]
        if not h or key in seen or len(h) > 160:
            continue
        seen.add(key)
        items.append({"headline": h, "source": n.get("source") or "", "url": n.get("url") or "",
                      "symbols": (n.get("symbols") or [])[:4], "created_at": n.get("created_at") or "",
                      "summary": re.sub(r"<[^>]+>", "", n.get("summary") or "").strip()[:500]})
    with _lock:
        _news_cache.update(at=time.time(), items=items)
    return items[:limit]


_REGIME = (("SPY", "US stocks"), ("TLT", "long-term Treasury bonds (falling means rising rates)"),
           ("UUP", "the US dollar"), ("USO", "oil"), ("GLD", "gold"), ("XLE", "energy stocks"), ("XLK", "tech stocks"))
_regime_cache: dict = {}


def regime(as_of: Optional[date] = None) -> str:
    """One line on what the market is signalling: 1- and 3-month moves of stocks, bonds, the dollar, oil, gold,
    using only prices up to as_of. Cached per day; "" if the data isn't available."""
    d = (as_of or today()).isoformat()
    if d in _regime_cache:
        return _regime_cache[d]
    bits = []
    for sym, label in _REGIME:
        try:
            dates, closes = daily_closes(sym)
            i = _index_on_or_before(dates, d)
            if i < 63:
                continue
            bits.append(f"{label} {_ret(closes, i, 21):+.1%} over 1 month, {_ret(closes, i, 63):+.1%} over 3 months")
        except Exception:
            continue
    line = "; ".join(bits)
    if len(_regime_cache) > 400:
        _regime_cache.clear()
    _regime_cache[d] = line
    return line
