# options_fetcher.py
# Contains functions to fetch live options data and refine strategies

import yfinance as yf
from datetime import datetime, timedelta

def get_current_price(ticker):
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    return data["Close"].iloc[-1]

def fetch_live_options_data(ticker):
    stock = yf.Ticker(ticker)
    expiry = stock.options[0]  # Earliest expiry
    chain = stock.option_chain(expiry)
    calls = chain.calls
    puts = chain.puts
    return calls, puts, expiry

def refine_spread(ticker, legs, refinement, direction):
    calls, puts, expiry = fetch_live_options_data(ticker)
    price = get_current_price(ticker)
    strike_step = 2.5 if price > 200 else 1  # rough adjustment granularity

    # Find ATM strike
    rounded = round(price / strike_step) * strike_step

    # Set base distance
    offset = 1 * strike_step
    if refinement == "more aggressive":
        offset = 2 * strike_step
    elif refinement == "safer":
        offset = 0.5 * strike_step

    if direction == "bullish":
        buy_strike = rounded
        sell_strike = rounded + offset
        new_legs = [f"Buy {ticker} {buy_strike}c", f"Sell {ticker} {sell_strike}c"]
    elif direction == "bearish":
        buy_strike = rounded
        sell_strike = rounded - offset
        new_legs = [f"Buy {ticker} {buy_strike}p", f"Sell {ticker} {sell_strike}p"]
    elif direction == "neutral":
        new_legs = [f"Buy {ticker} {rounded}c", f"Buy {ticker} {rounded}p"]
    else:
        new_legs = legs  # fallback to original

    return {
        "type": f"{legs[0].split()[0]} Spread (Live) (Refined)",
        "legs": new_legs,
        "expiry": expiry,
        "payout": "2.0x"
    }
