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
    vols: list[float] = []
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
            vols.append(float(b.get("v") or 0.0))
        page = data.get("next_page_token")
        if not page:
            break
    with _lock:
        _bars_cache[symbol] = (dates, closes)
        _vol_cache[symbol] = vols
        _bars_at[symbol] = _t.time()
    return dates, closes


_vol_cache: dict[str, list[float]] = {}


def daily_volumes(symbol: str) -> list[float]:
    """Daily share volume aligned with daily_closes(symbol). [] when unknown."""
    symbol = symbol.upper()
    dates, _ = daily_closes(symbol)
    with _lock:
        v = _vol_cache.get(symbol) or []
    return v if len(v) == len(dates) else []


def volume_profile(symbol: str, as_of: Optional[date] = None, window: int = 120, bins: int = 40) -> Optional[dict]:
    """Where the stock actually traded over the last `window` sessions, from daily bars (a daily approximation of an
    intraday volume profile): the most-traded price (POC) and the value area holding 70% of the volume (VAL..VAH).
    Uses only data up to as_of. None when volume isn't available."""
    dates, closes = daily_closes(symbol)
    vols = daily_volumes(symbol)
    if not vols:
        return None
    i = _index_on_or_before(dates, (as_of or today()).isoformat())
    if i < 40:
        return None
    lo_i = max(0, i - window + 1)
    px, vv = closes[lo_i: i + 1], vols[lo_i: i + 1]
    tot = sum(vv)
    lo, hi = min(px), max(px)
    if tot <= 0 or hi <= lo:
        return None
    w = (hi - lo) / bins
    hist = [0.0] * bins
    for p_, v_ in zip(px, vv):
        hist[min(bins - 1, int((p_ - lo) / w))] += v_
    poc_b = max(range(bins), key=lambda b: hist[b])
    a = b = poc_b
    acc = hist[poc_b]
    while acc < 0.7 * tot and (a > 0 or b < bins - 1):
        left = hist[a - 1] if a > 0 else -1.0
        right = hist[b + 1] if b < bins - 1 else -1.0
        if right >= left:
            b += 1; acc += hist[b]
        else:
            a -= 1; acc += hist[a]
    recent = vols[max(0, i - 4): i + 1]; base = vols[max(0, i - 59): i + 1]
    return {"poc": lo + (poc_b + 0.5) * w, "val": lo + a * w, "vah": lo + (b + 1) * w, "close": closes[i],
            "rvol": (sum(recent) / len(recent)) / (sum(base) / len(base)) if base and sum(base) > 0 else 1.0,
            "window": window}


def vp_features(symbol: str, as_of: Optional[date] = None) -> dict:
    """Volume-profile features (0 when unknown): where today's price sits versus where the stock has traded."""
    try:
        vp = volume_profile(symbol, as_of)
    except Exception:
        vp = None
    if not vp:
        return {"vp_poc_dist": 0.0, "vp_vah_dist": 0.0, "vp_val_dist": 0.0, "vp_above_value": 0.0, "vp_below_value": 0.0, "rvol": 1.0}
    c = vp["close"]
    return {"vp_poc_dist": c / vp["poc"] - 1, "vp_vah_dist": c / vp["vah"] - 1, "vp_val_dist": c / vp["val"] - 1,
            "vp_above_value": 1.0 if c > vp["vah"] else 0.0, "vp_below_value": 1.0 if c < vp["val"] else 0.0,
            "rvol": max(0.1, min(5.0, vp["rvol"]))}


# ---------------------------------------------------------------------------------------------------------------
# Trend lines.
#   SMA 20  - plain 20-day average: every day counts the same, so it turns late.
#   ALMA    - Arnaud Legoux Moving Average (Legoux & Kouzis-Loukas, 2009): weights on a fixed bell curve placed
#             near the newest days (offset 0.85, width n/6). Less lag and less noise than a plain average.
#   MuLine  - MuLabs' trend line. ALMA's bell curve, made adaptive, volume-aware and noise-proof:
#             1. the bell adapts to how cleanly the stock is moving (Kaufman's efficiency ratio over the window):
#                a clean trend pulls it onto the newest days and narrows it (turns sooner); a choppy tape widens
#                it (smoother);
#             2. each day is weighted by its volume versus the window's average (square root, capped 0.5..2x), so
#                moves with real money behind them count more than quiet drifts;
#             3. a noise band: the line's direction only flips once it pulls back from its high (or low) by more
#                than MU_BAND x the stock's normal daily move, so ordinary wiggles don't count as a turn.
#             On simulated markets (tuned on one set, checked on two fresh ones) it turned ~0.3-0.4 days sooner
#             than ALMA with ~15% fewer false turns. trendlab.py races all three on real histories; the Brain page
#             shows that result, whatever it is.
#   Each value uses only that day and the days before it.
TREND_N = 21                                       # days in the window (MuLine and ALMA)
ALMA_N, ALMA_OFFSET, ALMA_SIGMA = TREND_N, 0.85, 6.0
MU_OFFSET = (0.90, 0.99)                           # bell position: choppy .. clean trend (0 oldest, 1 newest)
MU_SIGMA = (6.0, 14.0)                             # bell narrowness (width = n / sigma): choppy .. clean trend
MU_VOL_CAP = (0.5, 2.0)
MU_BAND = 0.25                                     # noise band, in units of the stock's typical daily move
TREND_LOOKBACK = 60                                # days shown on the chart and used to count turns


def alma_weights(n: int = 9, offset: float = 0.85, sigma: float = 6.0) -> list[float]:
    """Normalised bell-curve weights, oldest day first (they sum to 1)."""
    m, s = offset * (n - 1), n / sigma
    w = [math.exp(-((k - m) ** 2) / (2 * s * s)) for k in range(n)]
    tot = sum(w)
    return [x / tot for x in w]


def alma(values: list[float], n: int = 9, offset: float = 0.85, sigma: float = 6.0) -> Optional[float]:
    """ALMA of the last n values (None if there are fewer than n)."""
    if len(values) < n:
        return None
    return sum(w * v for w, v in zip(alma_weights(n, offset, sigma), values[-n:]))


def alma_series(values: list[float], n: int = ALMA_N, offset: float = ALMA_OFFSET, sigma: float = ALMA_SIGMA) -> list[Optional[float]]:
    """ALMA at every day (None until there are n days)."""
    w = alma_weights(n, offset, sigma)
    return [None if t < n - 1 else sum(a * b for a, b in zip(w, values[t - n + 1: t + 1])) for t in range(len(values))]


def sma_series(values: list[float], n: int = 20) -> list[Optional[float]]:
    out, run = [], 0.0
    for t, v in enumerate(values):
        run += v
        if t >= n:
            run -= values[t - n]
        out.append(run / n if t >= n - 1 else None)
    return out


def efficiency(window: list[float]) -> float:
    """Kaufman's efficiency ratio: net move / total distance travelled (1 = straight line, ~0 = going nowhere)."""
    path = sum(abs(b - a) for a, b in zip(window, window[1:]))
    return abs(window[-1] - window[0]) / path if path > 0 else 0.0


def muline_weights(window: list[float], vols: Optional[list[float]] = None) -> list[float]:
    """MuLine's weights for one window (oldest day first, sum 1)."""
    n = len(window)
    er = efficiency(window)
    offset = MU_OFFSET[0] + (MU_OFFSET[1] - MU_OFFSET[0]) * er
    sigma = MU_SIGMA[0] + (MU_SIGMA[1] - MU_SIGMA[0]) * er
    m, s = offset * (n - 1), n / sigma
    w = [math.exp(-((k - m) ** 2) / (2 * s * s)) for k in range(n)]
    if vols and len(vols) == n:
        avg = sum(vols) / n
        if avg > 0:
            w = [x * max(MU_VOL_CAP[0], min(MU_VOL_CAP[1], math.sqrt(max(v, 0.0) / avg))) for x, v in zip(w, vols)]
    tot = sum(w)
    return [x / tot for x in w]


def muline_series(values: list[float], vols: Optional[list[float]] = None, n: int = TREND_N) -> list[Optional[float]]:
    """MuLine at every day (None until there are n days). vols: daily volume aligned with values, or None."""
    use_v = vols if vols and len(vols) == len(values) else None
    out: list[Optional[float]] = []
    for t in range(len(values)):
        if t < n - 1:
            out.append(None)
            continue
        win = values[t - n + 1: t + 1]
        w = muline_weights(win, use_v[t - n + 1: t + 1] if use_v else None)
        out.append(sum(a * b for a, b in zip(w, win)))
    return out


def slope_dirs(line: list[Optional[float]]) -> list[int]:
    """Plain direction of a line each day: +1 up, -1 down (a flat day keeps the last direction), 0 before it starts."""
    out, prev = [], 0
    for t, v in enumerate(line):
        if t and v is not None and line[t - 1] is not None:
            d = 1 if v > line[t - 1] else -1 if v < line[t - 1] else 0
            prev = d or prev
        out.append(prev if v is not None else 0)
    return out


def band_dirs(line: list[Optional[float]], px: list[float], k: float = MU_BAND, win: int = 20) -> list[int]:
    """MuLine's direction each day: it only flips once the line pulls back from its latest high (low) by more than
    k x the stock's typical daily move (stdev of the last `win` daily % changes) x the line's level."""
    out, d, ext = [], 0, None
    for t, v in enumerate(line):
        if v is None:
            out.append(0)
            continue
        if ext is None:
            ext = v
            out.append(0)
            continue
        rets = [px[j] / px[j - 1] - 1 for j in range(max(1, t - win + 1), t + 1) if px[j - 1] > 0]
        if len(rets) > 2:
            m = sum(rets) / len(rets)
            sd = math.sqrt(sum((r - m) ** 2 for r in rets) / len(rets))
        else:
            sd = 0.01
        thr = k * sd * v
        if d >= 0:
            if v > ext:
                ext = v
                d = d or 1
            elif v < ext - thr:
                d, ext = -1, v
        else:
            if v < ext:
                ext = v
            elif v > ext + thr:
                d, ext = 1, v
        out.append(d)
    return out


def dir_turns(dirs: list[int]) -> tuple[int, int, int]:
    """(direction now, days since it last turned, number of turns) from a daily direction list."""
    age, flips, prev = 0, 0, 0
    for d in dirs:
        if d and prev and d != prev:
            flips += 1
            age = 0
        prev = d or prev
        age += 1 if prev else 0
    return prev, age, flips


def _turns(line: list[float]) -> tuple[int, int, int]:
    """(direction now +1/-1/0, days since it last turned, number of turns) for a line with no gaps."""
    age, flips, prev = 0, 0, 0
    for a, b in zip(line, line[1:]):
        d = 1 if b > a else -1 if b < a else 0
        if d and prev and d != prev:  # a flat day neither continues nor breaks the run
            flips += 1
            age = 0
        prev = d or prev
        age += 1
    return prev, age, flips


def trend_state(symbol: str, as_of: Optional[date] = None, chart: bool = False) -> Optional[dict]:
    """The stock's trend from its MuLine, next to a plain 20-day average, using only data up to as_of."""
    dates, closes = daily_closes(symbol)
    i = _index_on_or_before(dates, (as_of or today()).isoformat())
    need = TREND_N + TREND_LOOKBACK
    if i < need:
        return None
    lo_i = max(0, i - need - 20 + 1)
    px = closes[lo_i: i + 1]
    vols = daily_volumes(symbol)
    vv = vols[lo_i: i + 1] if vols else None
    mu = muline_series(px, vv)
    sm = sma_series(px, 20)
    m_tail, s_tail = mu[-(TREND_LOOKBACK + 1):], sm[-(TREND_LOOKBACK + 1):]
    if any(v is None for v in m_tail) or any(v is None for v in s_tail):
        return None
    # the noise band needs a little run-up, so direction is worked out over everything we have, then the last 60 days
    dirs = band_dirs(mu, px)[-TREND_LOOKBACK:]
    if not any(dirs):
        return None
    m_dir, m_age, m_flips = dir_turns(dirs)
    s_dir, s_age, s_flips = _turns(s_tail)
    out = {"dir": m_dir, "age": m_age, "flips": m_flips, "close": px[-1], "line": m_tail[-1],
           "dist": px[-1] / m_tail[-1] - 1 if m_tail[-1] else 0.0,
           "slope5": m_tail[-1] / m_tail[-6] - 1 if m_tail[-6] else 0.0,
           "clean": round(efficiency(px[-TREND_N:]), 3), "volume_aware": bool(vv),
           "sma_dir": s_dir, "sma_age": s_age, "sma_flips": s_flips,
           "params": {"n": TREND_N, "sma": 20, "days": TREND_LOOKBACK}}
    if chart:
        k = len(px) - TREND_LOOKBACK
        out["chart"] = {"dates": dates[i - TREND_LOOKBACK + 1: i + 1], "close": [round(v, 2) for v in px[k:]],
                        "line": [round(v, 2) for v in mu[k:]], "sma": [round(v, 2) for v in sm[k:]], "dir": dirs}
    return out


TREND_KEYS = ("mu_dist", "mu_slope", "mu_up", "mu_age", "mu_flips")


def trend_features(symbol: str, as_of: Optional[date] = None) -> dict:
    """MuLine features (0 when unknown). mu_up: +1 rising, -1 falling; mu_age: days since it turned (0..1 = 0..60);
    mu_flips: how choppy (turns in the last 60 days / 10); mu_dist: price vs the line; mu_slope: its 5-day change."""
    try:
        t = trend_state(symbol, as_of)
    except Exception:
        t = None
    if not t:
        return {k: 0.0 for k in TREND_KEYS}
    return {"mu_dist": max(-0.5, min(0.5, t["dist"])), "mu_slope": max(-0.3, min(0.3, t["slope5"])),
            "mu_up": float(t["dir"]), "mu_age": min(t["age"], TREND_LOOKBACK) / TREND_LOOKBACK,
            "mu_flips": t["flips"] / 10.0}


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


def mom_12_1(closes: list[float], i: int) -> float:
    """12-1 momentum (Jegadeesh & Titman 1993): return from ~12 months ago to ~1 month ago, skipping the latest
    month (which tends to reverse). Equals (1 + mom250) / (1 + mom20) - 1."""
    if i < 250 or closes[i - 250] <= 0:
        return 0.0
    return closes[i - 20] / closes[i - 250] - 1.0


def fip_id(closes: list[float], i: int) -> float:
    """Information discreteness ("frog in the pan", Da, Gurun & Warachka 2014) over the 12-1 window:
    sign(12-1 return) * (% down days - % up days). Near -1 = the move came as many small steady steps
    (continuous, tends to persist); near +1 = it came from a few big jumps (discrete, tends to fade).
    0.0 when there is not a year of history."""
    if i < 250 or closes[i - 250] <= 0:
        return 0.0
    pret = closes[i - 20] / closes[i - 250] - 1.0
    ups = downs = n = 0
    for k in range(i - 249, i - 19):
        if closes[k - 1] <= 0:
            continue
        n += 1
        if closes[k] > closes[k - 1]:
            ups += 1
        elif closes[k] < closes[k - 1]:
            downs += 1
    if n == 0 or pret == 0:
        return 0.0
    return (1.0 if pret > 0 else -1.0) * (downs - ups) / n


def fip_features(symbol: str, as_of: Optional[date] = None) -> dict:
    """{"fip_id": ...} using closes up to as_of only."""
    dates, closes = daily_closes(symbol)
    i = _index_on_or_before(dates, (as_of or today()).isoformat())
    return {"fip_id": fip_id(closes, i) if i >= 0 else 0.0}


def resid_mom(dates: list[str], closes: list[float], sdates: list[str], scloses: list[float], i: int) -> float:
    """Residual momentum (Blitz, Huij & Martens 2011), market-model version over the 12-1 window: take the stock's
    daily returns from ~12 months ago to ~1 month ago, remove the part explained by SPY (beta fitted on that same
    window, alpha kept), and score the summed residual return per unit of residual risk:
    sum(e) / (std(e) * sqrt(n)). High = the stock outran what its market exposure explains, steadily.
    Uses only closes up to index i (as of the pick's date). 0.0 without ~a year of matched history."""
    if i < 250 or not sdates:
        return 0.0
    spx = {d: c for d, c in zip(sdates, scloses)}
    rs: list[float] = []
    ms: list[float] = []
    for k in range(i - 249, i - 19):
        a, b = closes[k - 1], closes[k]
        sa, sb = spx.get(dates[k - 1]), spx.get(dates[k])
        if a <= 0 or not sa or not sb or sa <= 0:
            continue
        rs.append(b / a - 1.0)
        ms.append(sb / sa - 1.0)
    n = len(rs)
    if n < 150:
        return 0.0
    mr, mm = sum(rs) / n, sum(ms) / n
    var_m = sum((x - mm) ** 2 for x in ms) / n
    beta = sum((x - mr) * (y - mm) for x, y in zip(rs, ms)) / n / var_m if var_m > 1e-12 else 0.0
    e = [x - beta * y for x, y in zip(rs, ms)]
    me = sum(e) / n
    sd = math.sqrt(sum((x - me) ** 2 for x in e) / (n - 1))
    if sd <= 1e-12:
        return 0.0
    return max(-10.0, min(10.0, sum(e) / (sd * math.sqrt(n))))


def resid_features(symbol: str, as_of: Optional[date] = None) -> dict:
    """{"resid_mom": ...} using closes (stock and SPY) up to as_of only."""
    dates, closes = daily_closes(symbol)
    sdates, scloses = daily_closes("SPY")
    i = _index_on_or_before(dates, (as_of or today()).isoformat())
    return {"resid_mom": resid_mom(dates, closes, sdates, scloses, i) if i >= 0 else 0.0}


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
        "mom_12_1": mom_12_1(closes, i),
        "fip_id": fip_id(closes, i),
        "resid_mom": resid_mom(dates, closes, sdates, scloses, i),
        "vol20": realized_vol(closes, i, 20),
        "vol60": vol60,
        "rs60": _ret(closes, i, 60) - (_ret(scloses, j, 60) if j >= 60 else 0.0),
        "dist_high": closes[i] / hi252 - 1.0 if hi252 > 0 else 0.0,
        "log_price": math.log(max(closes[i], 0.01)),
        "history_days": min(i, 1000),
        **vp_features(symbol, as_of),
        **regime_features(as_of),
        **trend_features(symbol, as_of),
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


_iv_cache: dict = {}
_OCC = re.compile(r"^([A-Z.]+)(\d{6})([CP])(\d{8})$")


def option_iv(underlying: str, kind: str, strike: float, expiration: date) -> Optional[float]:
    """The market's implied volatility for the listed contract closest to (kind, strike, expiration), from Alpaca's
    options snapshots (indicative feed). Real option prices bake in the volatility smile and skew that a single flat
    volatility misses. None when unavailable (callers fall back to historical volatility)."""
    import time as _t
    underlying = underlying.upper(); kind = kind.lower()
    key = (underlying, kind, expiration.isoformat())
    hit = _iv_cache.get(key)
    if not hit or _t.time() - hit[0] > 1800:
        params = {"feed": os.getenv("ALPACA_OPTIONS_FEED", "indicative"), "type": kind, "limit": 1000,
                  "expiration_date_gte": (expiration - timedelta(days=21)).isoformat(),
                  "expiration_date_lte": (expiration + timedelta(days=21)).isoformat()}
        rows = []
        try:
            r = _session.get(f"{_data_base()}/v1beta1/options/snapshots/{underlying}", headers=_headers(), params=params, timeout=10)
            if r.status_code == 200:
                for sym, snap in ((r.json() or {}).get("snapshots") or {}).items():
                    m = _OCC.match(sym)
                    iv = (snap or {}).get("impliedVolatility")
                    if not m or not iv or not (0.03 < float(iv) < 4.0):
                        continue
                    exp = date(2000 + int(m.group(2)[:2]), int(m.group(2)[2:4]), int(m.group(2)[4:6]))
                    rows.append((exp, int(m.group(4)) / 1000.0, float(iv)))
        except Exception:
            rows = []
        hit = (_t.time(), rows)
        _iv_cache[key] = hit
    rows = hit[1]
    if not rows:
        return None
    best = min(rows, key=lambda x: (abs((x[0] - expiration).days) / 30.0) + abs(x[1] - strike) / max(strike, 1.0) * 10)
    return best[2]


_state_cache: dict[str, dict] = {}


def regime_state(as_of: Optional[date] = None) -> dict:
    """Which of three market regimes we're in, from the S&P 500 only (prices up to as_of):
    crisis   - turbulent: 20-day volatility above 28% a year, or more than 12% below the 1-year high
    trending - steady climb: up more than 4% over 3 months with volatility under 22%
    calm     - everything else (sideways or quiet)
    Different stock-picking styles tend to work in different regimes; the brain tests that."""
    d = (as_of or today()).isoformat()
    if d in _state_cache:
        return _state_cache[d]
    try:
        dates, closes = daily_closes("SPY")
        i = _index_on_or_before(dates, d)
        if i < 63:
            raise MarketDataError("short history")
        vol = realized_vol(closes, i, 20)
        hi = max(closes[max(0, i - 251): i + 1])
        dd = closes[i] / hi - 1 if hi > 0 else 0.0
        r60 = _ret(closes, i, 60)
        name = "crisis" if (vol > 0.28 or dd < -0.12) else "trending" if (r60 > 0.04 and vol < 0.22) else "calm"
        out = {"regime": name, "spy_vol20": round(vol, 4), "spy_dd": round(dd, 4), "spy_r60": round(r60, 4)}
    except Exception:
        out = {"regime": "unknown", "spy_vol20": 0.0, "spy_dd": 0.0, "spy_r60": 0.0}
    if len(_state_cache) > 2000:
        _state_cache.clear()
    _state_cache[d] = out
    return out


def regime_features(as_of: Optional[date] = None) -> dict:
    r = regime_state(as_of)["regime"]
    return {"reg_trend": 1.0 if r == "trending" else 0.0, "reg_crisis": 1.0 if r == "crisis" else 0.0,
            "reg_calm": 1.0 if r == "calm" else 0.0}


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
