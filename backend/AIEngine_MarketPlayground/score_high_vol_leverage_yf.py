#!/usr/bin/env python3
"""
score_high_vol_leverage_yf.py

Sector-based high-vol, high-leverage options prototype using yfinance.

  • Fetches every call & put across all expiries for each ticker
  • Assigns expiry date & option type to each row
  • Computes mid-price and leverage ≈ (IV × underlying_price) / mid_price
  • Scores each contract as (volume × leverage)
  • Prints the top 10 contracts by score
"""

import yfinance as yf
import pandas as pd

# ── CONFIG: your sector tickers here ───────────────────────────────
SECTOR_TICKERS = [
    "AAPL",   # Apple (Tech)
    "MSFT",   # Microsoft
    "NVDA",   # Nvidia
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
]


def main():
    all_rows = []

    for sym in SECTOR_TICKERS:
        print(f"--- Fetching {sym} ---")
        tkr = yf.Ticker(sym)

        # Get the latest underlying price (last close)
        hist = tkr.history(period="1d")
        if hist.empty:
            print(f"  ❌ Couldn't fetch underlying for {sym}")
            continue
        underlying_price = hist["Close"].iloc[-1]

        # Iterate all expiration dates
        for exp in tkr.options:
            try:
                chain = tkr.option_chain(exp)
            except Exception:
                # skip if yfinance fails for this expiry
                continue

            # Make copies to avoid SettingWithCopyWarnings
            calls = chain.calls.copy()
            puts  = chain.puts.copy()

            # If neither side has data, skip
            if calls.empty and puts.empty:
                continue

            # Tag expiry, option type, and underlying symbol
            calls["expiry"]     = exp
            calls["optionType"] = "call"
            calls["underlying"] = sym

            puts["expiry"]      = exp
            puts["optionType"]  = "put"
            puts["underlying"]  = sym

            # Combine calls & puts into one DataFrame
            df = pd.concat([calls, puts], ignore_index=True)

            # Compute mid price and filter out zeros
            df["mid_price"] = (df["bid"] + df["ask"]) / 2
            df = df[df["mid_price"] > 0]

            # Compute theoretical leverage: (IV × underlying_price) / mid_price
            df["leverage"] = (df["impliedVolatility"].fillna(0) * underlying_price) / df["mid_price"]

            # Score = volume × leverage
            df["score"] = df["volume"].fillna(0) * df["leverage"]

            # Keep only the columns we care about
            df = df[[
                "underlying",
                "contractSymbol",
                "expiry",
                "strike",
                "optionType",
                "volume",
                "impliedVolatility",
                "bid",
                "ask",
                "leverage",
                "score",
            ]]

            all_rows.append(df)

    # If we got no data, exit
    if not all_rows:
        print("No data fetched.")
        return

    # Combine everything, sort by score, take top 10
    master = pd.concat(all_rows, ignore_index=True)
    top10 = master.sort_values("score", ascending=False).head(10)

    # Print results
    print("\n=== Top 10 High-Vol, High-Leverage Options ===")
    for idx, row in enumerate(top10.itertuples(index=False), 1):
        print(
            f"{idx:>2}. {row.underlying} {row.contractSymbol} | "
            f"Exp: {row.expiry} | Strike: {row.strike} | "
            f"{row.optionType} | Vol: {int(row.volume)} | "
            f"IV: {row.impliedVolatility:.2f} | Lev: {row.leverage:.2f} | "
            f"Score: {row.score:.1f}"
        )


if __name__ == "__main__":
    main()
