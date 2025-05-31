# collect_labels.py

import pandas as pd
import yfinance as yf

# 1) Path to the CSV where we store historical labels
OUTPUT_FILE = "historic_data.csv"

# ─────────────────────────────────────────────────────────────────────────────
# FOR TESTING: only label AAPL on the known, currently available expiry 2025-06-06
TICKERS   = ["AAPL"]
today_str = "2025-06-06"   # forced expiry for testing (must be in tkr.options)
# ─────────────────────────────────────────────────────────────────────────────

all_rows = []

for sym in TICKERS:
    tkr = yf.Ticker(sym)

    # If that forced expiry isn't in the ticker’s available options, skip.
    if today_str not in tkr.options:
        print(f"Skipping {sym}: expiry {today_str} not found in {tkr.options}")
        continue

    try:
        chain = tkr.option_chain(today_str)
    except Exception as e:
        print(f"Warning: could not fetch chain for {sym} {today_str}: {e}")
        continue

    # Get that day’s closing price for the underlying
    try:
        underlying_price = tkr.history(period="1d")["Close"].iloc[-1]
    except Exception as e:
        print(f"Warning: could not fetch closing price for {sym}: {e}")
        continue

    # Process calls
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

    # Process puts
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

# Convert the collected rows into a DataFrame
df_new = pd.DataFrame(all_rows)

# Try reading the existing CSV; if missing or empty, start fresh
try:
    df_old = pd.read_csv(OUTPUT_FILE)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
except (FileNotFoundError, pd.errors.EmptyDataError):
    df_all = df_new

# Overwrite (or create) the CSV
df_all.to_csv(OUTPUT_FILE, index=False)
print(f"Appended {len(df_new)} new rows to {OUTPUT_FILE}")
