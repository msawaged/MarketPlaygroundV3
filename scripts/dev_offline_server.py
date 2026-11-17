"""Run the API locally with NO network keys: fake Claude + synthetic prices for real tickers.

For walking signed-in screens (chat picks, options card, portfolio, My beliefs) on a laptop or in CI without
Anthropic/Alpaca keys. Prices are synthetic (deterministic random walks anchored near each stock's real level);
never point this at a real database.

    unset DATABASE_URL; MP_SQLITE_PATH=/tmp/mp_dev.db PYTHONPATH=./ python scripts/dev_offline_server.py
    cd frontend && VITE_API_BASE=http://127.0.0.1:8000 npx vite --port 5173
"""
import json
import math
import os
import random
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

if os.getenv("DATABASE_URL"):
    raise SystemExit("Refusing to run: DATABASE_URL is set. This server is for a throwaway SQLite only.")

from backend.v4 import interpreter, market  # noqa: E402

# Ticker -> (name, rough price level, yearly drift)
UNIVERSE = {
    "DAL": ("Delta Air Lines, Inc. Common Stock", 58.0, 0.10), "UAL": ("United Airlines Holdings, Inc.", 95.0, 0.12),
    "BKNG": ("Booking Holdings Inc. Common Stock", 5100.0, 0.15), "EXPE": ("Expedia Group, Inc.", 175.0, 0.08),
    "MAR": ("Marriott International", 260.0, 0.09), "ABNB": ("Airbnb, Inc.", 135.0, 0.02),
    "JETS": ("U.S. Global Jets ETF", 24.0, 0.05), "NVDA": ("NVIDIA Corporation Common Stock", 185.0, 0.35),
    "AMD": ("Advanced Micro Devices, Inc.", 240.0, 0.2), "AVGO": ("Broadcom Inc.", 340.0, 0.3),
    "SMH": ("VanEck Semiconductor ETF", 320.0, 0.25), "CMG": ("Chipotle Mexican Grill, Inc.", 38.0, -0.05),
    "DRI": ("Darden Restaurants, Inc.", 185.0, 0.0), "EAT": ("Brinker International, Inc.", 140.0, 0.1),
    "SPY": ("SPDR S&P 500 ETF Trust", 680.0, 0.1),
}
TOPICS = {
    "travel": ["DAL", "BKNG", "UAL", "EXPE", "MAR", "JETS"],
    "chip": ["NVDA", "AMD", "AVGO", "SMH"], "ai": ["NVDA", "AVGO", "AMD", "SMH"],
    "restaurant": ["CMG", "DRI", "EAT"],
}


def _series(sym: str):
    name, level, drift = UNIVERSE[sym]
    rnd = random.Random(sym)
    end = market.today()
    d = end - timedelta(days=365 * 5)
    days = [d + timedelta(days=i) for i in range((end - d).days + 1)]
    days = [x for x in days if x.weekday() < 5]
    path, p = [], 1.0
    for _ in days:
        p *= math.exp(drift / 252 + rnd.gauss(0, 0.018))
        path.append(p)
    scale = level / path[-1]
    return [x.isoformat() for x in days], [round(v * scale, 2) for v in path]


_cache = {}


def daily_closes(sym):
    sym = sym.upper()
    if sym not in UNIVERSE:
        raise market.MarketDataError(f"no data for {sym} (offline dev universe)")
    if sym not in _cache:
        _cache[sym] = _series(sym)
    return _cache[sym]


market.daily_closes = daily_closes
market.daily_volumes = lambda s: [1_000_000.0] * len(daily_closes(s)[0])
market.latest_price = lambda s: daily_closes(s)[1][-1]
market.asset_info = lambda s: ({"symbol": s.upper(), "name": UNIVERSE[s.upper()][0], "tradable": True, "fractionable": True,
                                "is_etf": market._looks_like_etf(UNIVERSE[s.upper()][0])} if s.upper() in UNIVERSE else None)
market.option_iv = lambda *a, **k: None
market.headlines = lambda limit=6: []
market.clock = lambda: market._fallback_clock()


def session_close_on(sym, d):
    """Offline stand-in for the expiration-day close (so expired practice options settle instead of waiting forever)."""
    if d >= market.today():
        return None
    days, closes = daily_closes(sym)
    got = [(x, c) for x, c in zip(days, closes) if x <= d.isoformat()]
    return got[-1] if got else None


market.session_close_on = session_close_on


def _bs(spot, k, years, vol, kind, r=0.038):
    if years <= 0:
        return max(0.0, (spot - k) if kind == "call" else (k - spot))
    nd = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
    d1 = (math.log(spot / k) + (r + vol * vol / 2) * years) / (vol * math.sqrt(years))
    d2 = d1 - vol * math.sqrt(years)
    c = spot * nd(d1) - k * math.exp(-r * years) * nd(d2)
    return c if kind == "call" else c - spot + k * math.exp(-r * years)


def option_chain_near(sym, strike, expiration, days=21, band=0.15):
    """Offline stand-in: weekly Friday expirations, Black-Scholes quotes at a flat 35% vol, 1-cent-wide markets
    on either side of a 2% spread. Lets Close Call and the options card be walked without a quote feed."""
    sym = sym.upper()
    if sym not in UNIVERSE:
        return []
    spot, t0 = market.latest_price(sym), market.today()
    step = 1.0 if spot < 25 else 2.5 if spot < 200 else 5.0 if spot < 500 else 10.0
    lo, hi = max(t0 + timedelta(days=1), expiration - timedelta(days=days)), expiration + timedelta(days=days)
    out, d = [], lo
    while d <= hi:
        if d.weekday() == 4:
            years = (d - t0).days / 365.0
            k = math.ceil(strike * (1 - band) / step) * step
            while k <= strike * (1 + band):
                for kind in ("call", "put"):
                    mid = max(0.01, _bs(spot, k, years, 0.35, kind))
                    occ = f"{sym}{d:%y%m%d}{'C' if kind == 'call' else 'P'}{int(round(k * 1000)):08d}"
                    out.append({"symbol": occ, "type": kind, "strike": k, "expiration": d,
                                "bid": round(mid * 0.99, 2), "ask": round(mid * 1.01 + 0.01, 2), "iv": 0.35})
                k += step
        d += timedelta(days=1)
    return out


def option_quote(occ):
    o = market.parse_occ(occ)
    if not o:
        return None
    row = next((r for r in option_chain_near(o["underlying"], o["strike"], o["expiration"], days=0, band=0.0001)
                if r["symbol"] == occ.upper()), None)
    return row and {"bid": row["bid"], "ask": row["ask"], "mid": round((row["bid"] + row["ask"]) / 2, 4), "t": None}


market.option_chain_near = option_chain_near
market.option_quote = option_quote


class FakeClaude:
    def __init__(self):
        self.messages = self

    def create(self, **kw):
        import re
        m = re.search(r"Belief: ([^\n\\]*)", json.dumps(kw.get("messages", "")))
        msg = (m.group(1) if m else "").lower()  # just the user's belief
        if "beliefs" in json.dumps(kw.get("extra_body", {})):
            out = {"beliefs": ["people will travel more next summer"]}
        else:
            key = next((k for k in TOPICS if k in msg), "travel")
            bear = any(w in msg for w in ("less", "fall", "drop", "crash", "cut back", "weak"))
            d = "bearish" if bear else "bullish"
            if any(w in msg for w in ("big move", "either way", "volatil")):
                d = "volatile"
            elif any(w in msg for w in ("sideways", "flat", "range")):
                d = "neutral"
            out = {
                "is_market_belief": True, "note": "", "summary": f"Demand linked to {key} {'weakens' if bear else 'grows'}." if d in ("bullish", "bearish") else f"{key} stocks {'make a big move either way' if d == 'volatile' else 'stay in a range'}.",
                "direction": d, "horizon_days": 120, "conviction": "medium", "themes": [key, "consumer spending"],
                "causal_chain": f"{key} demand {'falls' if bear else 'rises'} -> these companies' sales move with it.",
                "candidates": [{"ticker": t, "name": UNIVERSE[t][0], "exposure": "direct" if i < 2 else "beneficiary",
                                "direction": d, "rationale": f"Sales tied closely to {key}.", "score": 0.9 - i * 0.08}
                               for i, t in enumerate(TOPICS[key])],
            }
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0), stop_reason="end_turn")


interpreter._client = lambda: FakeClaude()

if __name__ == "__main__":
    import uvicorn
    from backend.app import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
