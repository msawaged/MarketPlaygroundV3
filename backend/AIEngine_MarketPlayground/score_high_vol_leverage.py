#!/usr/bin/env python3
"""
score_high_vol_leverage.py

Fetches all option contracts for a given sector,
computes daily-volume and theoretical-leverage scores,
and lists the top 10 highest-score trades.
"""

import os
from datetime import datetime, date
from polygon import RESTClient
from dotenv import load_dotenv

# ===== CONFIGURATION =====
# Replace this list with the tickers in YOUR target sector.
SECTOR_TICKERS = [
    "AAPL",  # Apple (Technology)
    "MSFT",  # Microsoft
    "NVDA",  # Nvidia
    "GOOGL", # Alphabet
    "AMZN",  # Amazon
]

# Weights for scoring—favour volume & leverage equally for now.
WEIGHTS = {
    "volume":   1.0,   # daily volume
    "leverage": 1.0,   # theoretical leverage
}


# ===== HELPERS =====
def load_api_key():
    load_dotenv()
    key = os.getenv("POLYGON_API_KEY")
    if not key:
        raise RuntimeError("Set POLYGON_API_KEY in your .env file")
    return key

def days_to_expiry(expiry_str: str) -> int:
    """Return days until expiry (minimum 1)."""
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return max((exp - date.today()).days, 1)

def compute_leverage(delta, underlying_price, bid, ask):
    """|Δ × underlying_price / mid_price|, or 0 if we can’t compute."""
    mid = (bid + ask) / 2 if (bid and ask) else 0
    if mid <= 0:
        return 0.0
    return abs(delta * underlying_price / mid)


def score_contract(client, underlying, contract):
    """
    Fetch a snapshot, extract daily volume and greeks,
    compute leverage, then return (score, volume, leverage).
    """
    snap = client.get_snapshot_option_contract(ticker=contract["ticker"])
    # Greeks object
    greeks = snap.greeks
    delta = greeks.delta or 0.0

    # Day’s volume
    volume = snap.day.volume or 0

    # Option quote bounds
    bid = snap.last_quote.bid or 0.0
    ask = snap.last_quote.ask or 0.0

    # Underlying price (we’ll grab the last ask of the equity)
    underlying_price = snap.underlying_asset.last_quote.ask or 0.0

    # Compute leverage
    lev = compute_leverage(delta, underlying_price, bid, ask)

    # Weighted score
    score = WEIGHTS["volume"] * volume + WEIGHTS["leverage"] * lev

    return score, volume, lev


# ===== MAIN ROUTINE =====
def main():
    client = RESTClient(api_key=load_api_key())
    all_results = []

    for sym in SECTOR_TICKERS:
        print(f"Fetching {sym}…")
        resp = client.get_options_contracts(symbol=sym, limit=5000)
        for c in resp.results:
            try:
                sc, vol, lev = score_contract(client, sym, c)
                all_results.append({
                    "underlying": sym,
                    "contract":   c["ticker"],
                    "expiry":     c["expiration_date"],
                    "strike":     c["strike_price"],
                    "type":       c["option_type"],
                    "volume":     vol,
                    "leverage":   lev,
                    "score":      sc,
                })
            except Exception:
                # skip any that error out
                continue

    # Sort descending and show top 10
    top10 = sorted(all_results, key=lambda x: x["score"], reverse=True)[:10]
    print("\n=== Top 10 High-Vol, High-Leverage Options ===")
    for i, o in enumerate(top10, 1):
        print(
            f"{i:>2}. {o['underlying']} {o['contract']} | "
            f"Exp: {o['expiry']} | Strike: {o['strike']} | "
            f"{o['type']} | Vol: {o['volume']} | Lev: {o['leverage']:.2f}"
        )


if __name__ == "__main__":
    main()
