# collect_labels.py

import pandas as pd
import yfinance as yf
from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
# This script labels all tickers with an expiry *equal to today*. It writes:
#   date,contractSymbol,underlying,optionType,strike,impliedVolatility,volume,mid_price,realizedPL
#
# Every time you run it, it will:
#   • Use today’s date (e.g., "2025-06-06") and check each ticker’s available expiries.
#   • If that date is in ticker.options, fetch the chain, compute realized P/L, and append.
#   • If ‘historic_data.csv’ is missing/empty, it will create a new one.
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_FILE = "historic_data.csv"

# 1) List all tickers you want to label whenever they expire today.
#    Feel free to add more symbols here.
TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "AMZN"
    # add additional tickers as needed, e.g. "TSLA", "META", etc.
]

# 2) Determine today's date in YYYY-MM-DD format:
today_str = date.today().strftime("%Y-%m-%d")

all_rows = []

for sym in TICKERS:
    tkr = yf.Ticker(sym)

    # 3) If today_str is not in this ticker's options, skip:
    if today_str not in tkr.options:
        # Uncomment the next line if you want to see which tickers had no expiry
        # print(f"Skipping {sym}: no {today_str} expiry (available: {tkr.options[:3]}...)")
        continue

    # 4) Fetch the option chain for today_str
    try:
        chain = tkr.option_chain(today_str)
    except Exception as e:
        print(f"Warning: could not fetch option chain for {sym} {today_str}: {e}")
        continue

    # 5) Fetch today’s closing price for the underlying (used as “settlement”)
    try:
        underlying_price = tkr.history(period="1d")["Close"].iloc[-1]
    except Exception as e:
        print(f"Warning: could not fetch closing price for {sym}: {e}")
        continue

    # 6) Process calls
    for _, row in chain.calls.iterrows():
        contract_symbol = row["contractSymbol"]
        strike          = row["strike"]
        premium         = (row["bid"] + row["ask"]) / 2
        intrinsic       = max(underlying_price - strike, 0)
        realized_pl     = intrinsic - premium

        all_rows.append({
            "date":              today_str,
            "contractSymbol":    contract_symbol,
            "underlying":        sym,
            "optionType":        "call",
            "strike":            strike,
            "impliedVolatility": row["impliedVolatility"],
            "volume":            row["volume"],
            "mid_price":         premium,
            "realizedPL":        realized_pl
        })

    # 7) Process puts
    for _, row in chain.puts.iterrows():
        contract_symbol = row["contractSymbol"]
        strike          = row["strike"]
        premium         = (row["bid"] + row["ask"]) / 2
        intrinsic       = max(strike - underlying_price, 0)
        realized_pl     = intrinsic - premium

        all_rows.append({
            "date":              today_str,
            "contractSymbol":    contract_symbol,
            "underlying":        sym,
            "optionType":        "put",
            "strike":            strike,
            "impliedVolatility": row["impliedVolatility"],
            "volume":            row["volume"],
            "mid_price":         premium,
            "realizedPL":        realized_pl
        })

# 8) Convert to DataFrame
df_new = pd.DataFrame(all_rows)

# 9) Append to existing CSV (if it exists and is non-empty), else start fresh
try:
    df_old = pd.read_csv(OUTPUT_FILE)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
except (FileNotFoundError, pd.errors.EmptyDataError):
    df_all = df_new

# 10) Overwrite / create the CSV
df_all.to_csv(OUTPUT_FILE, index=False)

print(f"[collect_labels.py] Date={today_str} → Appended {len(df_new)} new rows to {OUTPUT_FILE}")
