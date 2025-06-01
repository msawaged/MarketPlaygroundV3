# collect_labels.py

import os
import pandas as pd
import numpy as np
import yfinance as yf
from pandas.tseries.offsets import BDay
from datetime import datetime

# Path to your historic data CSV
DATA_FILE = "historic_data.csv"

# List of underlyings to collect (equities, ETFs, etc.)
underlyings = [
    "AAPL",   # Apple Inc.
    "NVDA",   # NVIDIA Corporation
    "TSLA",   # Tesla, Inc.
    "SPY",    # SPDR S&P 500 ETF
    "TLT",    # iShares 20+ Year Treasury Bond ETF
    # You can add additional tickers here
]

def get_label_date() -> str:
    """
    Determine the "label date" for collecting underlying prices.
    - If today is a weekday (Mon-Fri), return today's date.
    - If today is Saturday or Sunday, roll back to the previous business day (Friday).
    Returns the date as an ISO-formatted string (YYYY-MM-DD).
    """
    today = pd.Timestamp.now().date()
    # weekday(): Monday=0, Tuesday=1, ..., Saturday=5, Sunday=6
    if today.weekday() >= 5:
        # If Saturday or Sunday, subtract one business day (i.e., go to Friday)
        previous_bday = pd.Timestamp(today) - BDay(1)
        return previous_bday.date().isoformat()
    else:
        # Otherwise, use today directly
        return today.isoformat()

def append_rows(df_new: pd.DataFrame):
    """
    Append new rows to historic_data.csv. If the file does not exist, create it with headers.
    """
    if not os.path.isfile(DATA_FILE):
        # First time running: write with headers
        df_new.to_csv(DATA_FILE, index=False)
    else:
        # Append without writing headers again
        df_new.to_csv(DATA_FILE, mode="a", header=False, index=False)

def get_underlying_return(symbol: str, label_date: str, expiry: str) -> float:
    """
    Compute the percent return of the underlying between label_date and expiry.
    - Attempts to fetch historical close prices from yfinance.
    - If label_date is not in the history, uses the first available row.
    - If expiry is not in the history, uses the last available row.
    Returns a float (e.g., 0.05 for +5%) or np.nan if data is unavailable.
    """
    tkr = yf.Ticker(symbol)
    try:
        # Download history from label_date to expiry (yfinance uses [start, end) convention)
        hist = tkr.history(start=label_date, end=expiry)
    except Exception:
        # If yfinance cannot fetch the history (e.g., delisted), return NaN
        return np.nan

    if hist.empty:
        # No rows returned → cannot compute return
        return np.nan

    # Attempt to get the close at the label date
    try:
        price_label = hist.loc[label_date]["Close"]
    except KeyError:
        # If exact label_date not in index, use the first available row
        price_label = hist["Close"].iloc[0]

    # Attempt to get the close at (or before) the expiry date
    try:
        price_expiry = hist.loc[expiry]["Close"]
    except KeyError:
        # If exact expiry not in index, use the last available row
        price_expiry = hist["Close"].iloc[-1]

    if price_label == 0:
        # Avoid division by zero
        return np.nan

    return (price_expiry / price_label) - 1

def collect_for_symbol(symbol: str, label_date: str) -> pd.DataFrame:
    """
    Fetch all option contracts for a single underlying (symbol) as of label_date.
    - Loops through each expiry in the option chain.
    - Computes underlyingReturn for that expiry.
    - Extracts option data (calls and puts) including openInterest and mid_price.
    - Builds and returns a DataFrame of new rows to append.
    If no valid data is found, returns an empty DataFrame.
    """
    tkr = yf.Ticker(symbol)
    try:
        expirations = tkr.options  # list of expiration dates as strings
    except Exception:
        # No options available for this symbol
        return pd.DataFrame()

    all_rows = []

    for expiry in expirations:
        # Compute underlying return from label_date to expiry
        underlying_return = get_underlying_return(symbol, label_date, expiry)
        if np.isnan(underlying_return):
            # Skip this expiry if return cannot be computed
            continue

        # Fetch the option chain for this expiry
        try:
            chain = tkr.option_chain(expiry)
            calls = chain.calls
            puts = chain.puts
        except Exception:
            # If yfinance fails (e.g., chain not found), skip
            continue

        # Process calls and puts separately
        for df_side, opt_type in [(calls, "call"), (puts, "put")]:
            if df_side.empty:
                continue

            # Ensure the required columns exist
            required_cols = ["contractSymbol", "strike", "impliedVolatility",
                             "volume", "bid", "ask", "openInterest"]
            if not all(col in df_side.columns for col in required_cols):
                continue

            # Compute mid_price as average of bid and ask
            df_side["mid_price"] = (df_side["bid"] + df_side["ask"]) / 2

            # For label collection, we set realizedPL = 0.0 (to be backfilled later)
            df_side["realizedPL"] = 0.0

            # Build a DataFrame for all rows of this side (calls or puts)
            df_new = pd.DataFrame({
                "date": label_date,
                "contractSymbol": df_side["contractSymbol"],
                "underlying": symbol,
                "optionType": opt_type,
                "strike": df_side["strike"],
                "impliedVolatility": df_side["impliedVolatility"],
                "volume": df_side["volume"],
                "mid_price": df_side["mid_price"],
                "realizedPL": df_side["realizedPL"],
                "openInterest": df_side["openInterest"],
                "underlyingReturn": underlying_return,
                "assetType": symbol
            })

            all_rows.append(df_new)

    if not all_rows:
        return pd.DataFrame()

    # Concatenate all collected rows for this symbol
    return pd.concat(all_rows, ignore_index=True)

def main():
    """
    Main entry point:
    1. Determine the correct label_date (roll back to Friday if weekend).
    2. Loop over each underlying and collect new rows.
    3. Append all new rows to historic_data.csv.
    """
    label_date = get_label_date()
    print(f"[collect_labels.py] Using labelDate = {label_date}")

    collected = []
    for symbol in underlyings:
        df_sym = collect_for_symbol(symbol, label_date)
        if not df_sym.empty:
            collected.append(df_sym)

    if not collected:
        print("[collect_labels.py] No new rows to append for any symbol.")
        return

    # Concatenate all symbols’ data into one DataFrame
    df_all = pd.concat(collected, ignore_index=True)
    append_rows(df_all)
    print(f"[collect_labels.py] Date={label_date} → Appended {len(df_all)} new rows to {DATA_FILE}")

if __name__ == "__main__":
    main()
