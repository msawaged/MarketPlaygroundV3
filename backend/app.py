# app.py

# ───────────────────────────────────────────────────────────────────────────────
# Imports and Setup
# ───────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime
import io
import re

import pandas as pd
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt

from ai_engine import process_prompt   # Your AI‐strategy prompt processor
import joblib                          # To load the trained ML model

app = FastAPI(title="MarketPlayground Engine")

# ───────────────────────────────────────────────────────────────────────────────
# Load Trained Machine Learning Model
# ───────────────────────────────────────────────────────────────────────────────
# Attempt to load 'best_model.joblib' from the same directory.
# If not found, we set model = None and fall back to heuristic ranking.
try:
    model = joblib.load("best_model.joblib")
    print("Loaded trained model from best_model.joblib")
except FileNotFoundError:
    print("WARNING: best_model.joblib not found. /strategy will fall back to heuristic.")
    model = None

# ───────────────────────────────────────────────────────────────────────────────
# Pydantic Models (Request and Response Schemas)
# ───────────────────────────────────────────────────────────────────────────────
class StrategyRequest(BaseModel):
    belief: str

class OptionContract(BaseModel):
    underlying: str
    contractSymbol: str
    expiry: str
    strike: float
    optionType: str
    volume: int
    impliedVolatility: float
    mid_price: float
    leverage: float
    score: float
    # The ML‐predicted P/L (if model loaded) will be included dynamically,
    # but Pydantic will ignore unexpected extra fields when serializing.

class StrategyResponse(BaseModel):
    suggestion: dict
    topContracts: List[OptionContract]

class PnlPoint(BaseModel):
    timestamp: str
    pnl: float

# ───────────────────────────────────────────────────────────────────────────────
# Core Scoring Logic
# ───────────────────────────────────────────────────────────────────────────────
# SECTOR_TICKERS lists the symbols we scan each time /strategy is called.
SECTOR_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

def fetch_and_score() -> pd.DataFrame:
    """
    Fetch today’s option chains for each ticker in SECTOR_TICKERS,
    compute a simple “score = volume × leverage,” and return a
    concatenated DataFrame sorted by score descending.
    Each DataFrame row has columns:
      ['underlying','contractSymbol','expiry','strike','optionType',
       'volume','impliedVolatility','mid_price','leverage','score']
    """
    rows = []

    for sym in SECTOR_TICKERS:
        tkr = yf.Ticker(sym)

        # 1) Get today’s closing price (spot). Skip if no data.
        hist = tkr.history(period="1d")
        if hist.empty:
            continue
        spot = hist["Close"].iloc[-1]

        # 2) Loop through each expiry for this ticker
        for exp in tkr.options:
            try:
                chain = tkr.option_chain(exp)
            except Exception:
                # If Yahoo does not have that chain, skip to next expiry
                continue

            # Process calls
            calls_df = chain.calls.copy()
            if not calls_df.empty:
                calls_df["underlying"] = sym
                calls_df["expiry"] = exp
                calls_df["optionType"] = "call"
                # mid_price = (bid + ask) / 2
                calls_df["mid_price"] = (calls_df["bid"] + calls_df["ask"]) / 2
                # Filter out zero‐priced contracts (no meaningful mid_price)
                calls_df = calls_df[calls_df["mid_price"] > 0]
                # Leverage = (IV * spot) / mid_price
                calls_df["leverage"] = (calls_df["impliedVolatility"].fillna(0) * spot) / calls_df["mid_price"]
                # Score = volume * leverage
                calls_df["score"] = calls_df["volume"].fillna(0) * calls_df["leverage"]
                rows.append(calls_df[[
                    "underlying","contractSymbol","expiry","strike",
                    "optionType","volume","impliedVolatility",
                    "mid_price","leverage","score"
                ]])

            # Process puts
            puts_df = chain.puts.copy()
            if not puts_df.empty:
                puts_df["underlying"] = sym
                puts_df["expiry"] = exp
                puts_df["optionType"] = "put"
                puts_df["mid_price"] = (puts_df["bid"] + puts_df["ask"]) / 2
                puts_df = puts_df[puts_df["mid_price"] > 0]
                puts_df["leverage"] = (puts_df["impliedVolatility"].fillna(0) * spot) / puts_df["mid_price"]
                puts_df["score"] = puts_df["volume"].fillna(0) * puts_df["leverage"]
                rows.append(puts_df[[
                    "underlying","contractSymbol","expiry","strike",
                    "optionType","volume","impliedVolatility",
                    "mid_price","leverage","score"
                ]])

    # If no option data at all, return an empty DataFrame
    if not rows:
        return pd.DataFrame()

    # Concatenate and sort by score descending
    master = pd.concat(rows, ignore_index=True)
    return master.sort_values("score", ascending=False)

# ───────────────────────────────────────────────────────────────────────────────
# Strategy Endpoint
# ───────────────────────────────────────────────────────────────────────────────
@app.post("/strategy", response_model=StrategyResponse)
def strategy_endpoint(req: StrategyRequest):
    """
    1) Use the AI engine (process_prompt) to get a “suggestion” dict.
    2) Call fetch_and_score() to retrieve & score all current chains.
    3) If a trained model is loaded, use model.predict(...) to compute 'predictedPL'
       for each contract and sort by it descending.
       Otherwise, fall back to sorting by the original 'score' heuristic.
    4) Return the top 10 contracts as JSON.
    """
    # 1) Get AI suggestion based on user belief
    suggestion = process_prompt(req.belief)

    # 2) Score all contracts
    df = fetch_and_score()
    if df.empty:
        raise HTTPException(status_code=500, detail="No options fetched for scoring")

    # 3) If ML model is loaded, predict realized P/L and sort by it
    if model is not None:
        # Extract features in the exact order: impliedVolatility, volume, mid_price
        features = df[["impliedVolatility", "volume", "mid_price"]].to_numpy()
        try:
            preds = model.predict(features)
        except Exception as e:
            # If prediction fails, log and fall back to heuristic
            print("Model prediction error:", e)
            preds = None

        if preds is not None:
            df["predictedPL"] = preds
            df_sorted = df.sort_values("predictedPL", ascending=False)
        else:
            df_sorted = df.sort_values("score", ascending=False)
    else:
        # No model loaded: use original heuristic
        df_sorted = df.sort_values("score", ascending=False)

    # 4) Return top 10
    top10 = df_sorted.head(10).to_dict(orient="records")
    return StrategyResponse(suggestion=suggestion, topContracts=top10)

# ───────────────────────────────────────────────────────────────────────────────
# Intraday P/L Endpoint
# ───────────────────────────────────────────────────────────────────────────────
@app.get("/live-pnl", response_model=List[PnlPoint])
def live_pnl_endpoint(contract: str):
    """
    Given a contractSymbol (e.g. “NVDA250606C00140000”):
    1) Extract “underlying” (letters prefix) and expiry (YYMMDD → YYYY-MM-DD).
    2) Download the option chain for that expiry, add "optionType" column.
    3) Locate the specific contract’s row to get premium, strike, type.
    4) Fetch intraday 5-min bars for the underlying; compute intrinsic value
       at each timestamp, P/L = intrinsic – premium.
    5) Return a list of {timestamp, pnl} points as JSON.
    """
    # 1) Parse underlying from the contract symbol (letters only)
    m = re.match(r"^([A-Za-z]+)", contract)
    if not m:
        raise HTTPException(status_code=400, detail="Invalid contract symbol")
    underlying = m.group(1)

    # 2) Extract YYMMDD from contract, convert to YYYY-MM-DD
    exp_code = contract[len(underlying) : len(underlying) + 6]  # e.g. "250606"
    try:
        expiry = datetime.strptime(exp_code, "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid expiry code: {exp_code}")

    # 3) Fetch the option chain for that expiry
    try:
        chain = yf.Ticker(underlying).option_chain(expiry)
    except ValueError as e:
        # Happens if the expiry isn’t available
        raise HTTPException(status_code=404, detail=str(e))

    # Add "optionType" before concatenating calls and puts
    calls = chain.calls.copy()
    calls["optionType"] = "call"
    puts = chain.puts.copy()
    puts["optionType"] = "put"
    df = pd.concat([calls, puts], ignore_index=True)

    # 4) Find the exact row for contractSymbol
    row = df[df["contractSymbol"] == contract]
    if row.empty:
        raise HTTPException(status_code=404, detail="Contract not found in chain")

    premium = float((row["bid"].iloc[0] + row["ask"].iloc[0]) / 2)
    strike = float(row["strike"].iloc[0])
    opt_type = row["optionType"].iloc[0]

    # 5) Fetch intraday 5-minute bars for the underlying for "today"
    hist = yf.Ticker(underlying).history(period="1d", interval="5m")
    if hist.empty:
        raise HTTPException(status_code=404, detail="No intraday data available")

    # 6) Compute P/L at each timestamp
    result = []
    for ts, price in hist["Close"].items():
        if opt_type == "call":
            intrinsic = max(price - strike, 0)
        else:  # put
            intrinsic = max(strike - price, 0)

        pnl = intrinsic - premium
        result.append(PnlPoint(timestamp=ts.isoformat(), pnl=float(pnl)))

    return result

# ───────────────────────────────────────────────────────────────────────────────
# Expiry Payoff Chart Endpoint
# ───────────────────────────────────────────────────────────────────────────────
@app.get("/chart/expiry")
def chart_expiry(contract: str):
    """
    Returns a PNG plotting the expiry payoff curve for the given contractSymbol.
    1) Use fetch_and_score() to find the contract and its details (mid_price, strike, type).
    2) Determine current spot price (today’s close).
    3) Build a price grid around spot (±30%).
    4) Compute payoff = max(S-K,0) or max(K-S,0) minus mid_price.
    5) Plot curve, stream PNG back to caller.
    """
    # 1) Find the contract in the scored DataFrame
    df = fetch_and_score()
    rec = df[df["contractSymbol"] == contract]
    if rec.empty:
        raise HTTPException(status_code=404, detail="Contract not found or no longer available")

    top = rec.iloc[0]
    underlying = top["underlying"]

    # 2) Current spot price (use today’s close)
    hist_spot = yf.Ticker(underlying).history(period="1d")
    if hist_spot.empty:
        raise HTTPException(status_code=404, detail="No spot price available")
    spot = hist_spot["Close"].iloc[-1]

    # 3) Build price grid from 70% to 130% of spot
    prices = np.linspace(spot * 0.7, spot * 1.3, 200)

    # 4) Compute payoff curve
    if top["optionType"] == "call":
        payoffs = np.maximum(prices - top["strike"], 0) - top["mid_price"]
    else:  # put
        payoffs = np.maximum(top["strike"] - prices, 0) - top["mid_price"]

    # 5) Plot using Matplotlib
    fig, ax = plt.subplots()
    ax.plot(prices, payoffs, label="Payoff at Expiry")
    ax.axvline(spot, color="gray", linestyle="--", label=f"Spot = ${spot:.2f}")
    ax.set_xlabel("Underlying Price at Expiry ($)")
    ax.set_ylabel("P/L ($)")
    ax.set_title(f"{contract} Expiry Payoff")
    ax.legend()

    # Stream the figure as PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return StreamingResponse(buf, media_type="image/png")

# ───────────────────────────────────────────────────────────────────────────────
# Intraday P/L Chart Endpoint
# ───────────────────────────────────────────────────────────────────────────────
@app.get("/chart/pnl")
def chart_pnl(contract: str):
    """
    Returns a PNG plotting the intraday P/L curve for the given contractSymbol.
    1) Reuse live_pnl_endpoint to get timestamped P/L points.
    2) Plot P/L vs. time, stream PNG back to caller.
    """
    # 1) Get P/L points (raises HTTPException if any issue)
    pts = live_pnl_endpoint(contract)

    times = [p.timestamp for p in pts]
    values = [p.pnl for p in pts]

    # 2) Plot
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(times, values, marker="o", linestyle="-", label="Intraday P/L")
    # Show around 10 tick labels evenly spaced
    if len(times) > 10:
        step = len(times) // 10
    else:
        step = 1

    ax.set_xticks(times[::step])
    ax.set_xticklabels([t.split("T")[1][:5] for t in times[::step]], rotation=45)
    ax.set_xlabel("Time (HH:MM)")
    ax.set_ylabel("P/L ($)")
    ax.set_title(f"{contract} Intraday P/L")
    ax.grid(True)
    ax.legend()

    # Stream the figure as PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return StreamingResponse(buf, media_type="image/png")
# ─────────────────────────────────────────────────────────────────────
# Temporary endpoint to trigger label collection (testing only)
# ─────────────────────────────────────────────────────────────────────
from fastapi import BackgroundTasks

@app.post("/collect-labels")
def collect_labels_endpoint(background_tasks: BackgroundTasks):
    """
    This endpoint runs collect_labels.py in a background task,
    so you can just hit it with curl and the CSV will be populated.
    """
    def _run_labels():
        import subprocess
        subprocess.run(["python", "collect_labels.py"])

    background_tasks.add_task(_run_labels)
    return {"status": "Label collection started (watch console for output)."}

# ─────────────────────────────────────────────────────────────────────
