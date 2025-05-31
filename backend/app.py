# app.py
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

# ── AI engine import ────────────────────────────────────────────
# Make sure ai_engine.py lives alongside this file
from ai_engine import process_prompt

app = FastAPI(title="MarketPlayground Engine")

# ── Pydantic models ─────────────────────────────────────────────
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

class StrategyResponse(BaseModel):
    suggestion: dict
    topContracts: List[OptionContract]

class PnlPoint(BaseModel):
    timestamp: str
    pnl: float

# ── Core scoring logic ──────────────────────────────────────────
SECTOR_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

def fetch_and_score() -> pd.DataFrame:
    rows = []
    for sym in SECTOR_TICKERS:
        tkr = yf.Ticker(sym)
        hist = tkr.history(period="1d")
        if hist.empty:
            continue
        spot = hist["Close"].iloc[-1]

        for exp in tkr.options:
            try:
                chain = tkr.option_chain(exp)
            except:
                continue
            for df, opt_type in [(chain.calls, "call"), (chain.puts, "put")]:
                df = df.copy()
                if df.empty:
                    continue

                df["underlying"] = sym
                df["expiry"] = exp
                df["optionType"] = opt_type
                df["mid_price"] = (df["bid"] + df["ask"]) / 2
                df = df[df["mid_price"] > 0]

                df["leverage"] = (df["impliedVolatility"].fillna(0) * spot) / df["mid_price"]
                df["score"] = df["volume"].fillna(0) * df["leverage"]

                rows.append(df[[
                    "underlying", "contractSymbol", "expiry", "strike",
                    "optionType", "volume", "impliedVolatility",
                    "mid_price", "leverage", "score"
                ]])

    if not rows:
        return pd.DataFrame()
    master = pd.concat(rows, ignore_index=True)
    return master.sort_values("score", ascending=False)

# ── Strategy endpoint ───────────────────────────────────────────
@app.post("/strategy", response_model=StrategyResponse)
def strategy_endpoint(req: StrategyRequest):
    # 1) AI suggestion
    suggestion = process_prompt(req.belief)

    # 2) Score & pick top 10
    df = fetch_and_score()
    if df.empty:
        raise HTTPException(500, "No options fetched")
    top10 = df.head(10).to_dict(orient="records")
    return StrategyResponse(suggestion=suggestion, topContracts=top10)

# ── Intraday P/L JSON ───────────────────────────────────────────
@app.get("/live-pnl", response_model=List[PnlPoint])
def live_pnl_endpoint(contract: str):
    m = re.match(r"^([A-Za-z]+)", contract)
    if not m:
        raise HTTPException(400, "Invalid contract symbol")
    underlying = m.group(1)

    exp_code = contract[len(underlying):len(underlying)+6]  # YYMMDD
    expiry = datetime.strptime(exp_code, "%y%m%d").strftime("%Y-%m-%d")
    chain = yf.Ticker(underlying).option_chain(expiry)
    df = pd.concat([chain.calls, chain.puts], ignore_index=True)
    row = df[df["contractSymbol"] == contract]
    if row.empty:
        raise HTTPException(404, "Contract not found")

    premium = float((row["bid"].iloc[0] + row["ask"].iloc[0]) / 2)
    strike = float(row["strike"].iloc[0])
    opt_type = row["optionType"].iloc[0]

    hist = yf.Ticker(underlying).history(period="1d", interval="5m")
    if hist.empty:
        raise HTTPException(404, "No intraday data")

    result = []
    for ts, price in hist["Close"].items():
        intrinsic = max((price - strike), 0) if opt_type == "call" else max((strike - price), 0)
        pnl = intrinsic - premium
        result.append(PnlPoint(timestamp=ts.isoformat(), pnl=float(pnl)))
    return result

# ── Expiry Payoff chart ──────────────────────────────────────────
@app.get("/chart/expiry")
def chart_expiry(contract: str):
    # find the contract in scored DataFrame
    df = fetch_and_score()
    rec = df[df["contractSymbol"] == contract]
    if rec.empty:
        raise HTTPException(404, "Contract not found")
    top = rec.iloc[0]

    spot = yf.Ticker(top["underlying"]).history(period="1d")["Close"].iloc[-1]
    prices = np.linspace(spot * 0.7, spot * 1.3, 200)
    if top["optionType"] == "call":
        payoffs = np.maximum(prices - top["strike"], 0) - top["mid_price"]
    else:
        payoffs = np.maximum(top["strike"] - prices, 0) - top["mid_price"]

    fig, ax = plt.subplots()
    ax.plot(prices, payoffs)
    ax.axvline(spot, color="gray", linestyle="--")
    ax.set_xlabel("Price at Expiry")
    ax.set_ylabel("P/L ($)")
    ax.set_title(f"{contract} Expiry Payoff")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return StreamingResponse(buf, media_type="image/png")

# ── Intraday P/L chart ───────────────────────────────────────────
@app.get("/chart/pnl")
def chart_pnl(contract: str):
    # reuse JSON endpoint logic
    pts = live_pnl_endpoint(contract)
    times = [p.timestamp for p in pts]
    values = [p.pnl for p in pts]

    fig, ax = plt.subplots()
    ax.plot(times, values)
    ax.set_xticklabels([t.split("T")[1][:5] for t in times], rotation=45)
    ax.set_xlabel("Time")
    ax.set_ylabel("P/L ($)")
    ax.set_title(f"{contract} Intraday P/L")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return StreamingResponse(buf, media_type="image/png")
