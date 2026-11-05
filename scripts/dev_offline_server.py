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
            out = {
                "is_market_belief": True, "note": "", "summary": f"Demand linked to {key} {'weakens' if bear else 'grows'}.",
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
