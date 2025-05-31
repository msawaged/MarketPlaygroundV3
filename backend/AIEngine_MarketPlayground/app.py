# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from ai_engine import process_prompt
import yfinance as yf
import pandas as pd
import re
from datetime import datetime

app = FastAPI(title="MarketPlayground Engine")

# ── Request/Response Models ──────────────────────────────────────
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

# ── Core scoring logic (copied from your prototype) ───────────────
SECTOR_TICKERS = ["AAPL","MSFT","NVDA","GOOGL","AMZN"]

def fetch_and_score() -> pd.DataFrame:
    rows = []
    for sym in SECTOR_TICKERS:
        tkr = yf.Ticker(sym)
        hist = tkr.history(period="1d")
        if hist.empty: continue
        spot = hist["Close"].iloc[-1]

        for exp in tkr.options:
            try:
                chain = tkr.option_chain(exp)
            except:
                continue
            for df, opt_type in [(chain.calls, "call"), (chain.puts, "put")]:
                df = df.copy()
                if df.empty: continue

                df["underlying"]  = sym
                df["expiry"]      = exp
                df["optionType"]  = opt_type
                df["mid_price"]   = (df["bid"] + df["ask"]) / 2
                df = df[df["mid_price"] > 0]

                df["leverage"] = (df["impliedVolatility"].fillna(0) * spot) / df["mid_price"]
                df["score"]    = df["volume"].fillna(0) * df["leverage"]

                rows.append(df[[
                    "underlying","contractSymbol","expiry","strike",
                    "optionType","volume","impliedVolatility",
                    "mid_price","leverage","score"
                ]])

    if not rows:
        return pd.DataFrame()
    master = pd.concat(rows, ignore_index=True)
    return master.sort_values("score", ascending=False)

# ── Endpoints ────────────────────────────────────────────────────
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

@app.get("/live-pnl", response_model=List[PnlPoint])
def live_pnl_endpoint(contract: str):
    # Parse underlying from contractSymbol
    m = re.match(r"^([A-Za-z]+)", contract)
    if not m:
        raise HTTPException(400, "Invalid contract symbol")
    underlying = m.group(1)

    # Get initial premium
    exp_code = contract[len(underlying):len(underlying)+6]  # YYMMDD
    expiry = datetime.strptime(exp_code, "%y%m%d").strftime("%Y-%m-%d")
    chain = yf.Ticker(underlying).option_chain(expiry)
    df = pd.concat([chain.calls, chain.puts], ignore_index=True)
    row = df[df["contractSymbol"] == contract]
    if row.empty:
        raise HTTPException(404, "Contract not found")
    premium = float((row["bid"].iloc[0] + row["ask"].iloc[0]) / 2)
    strike   = float(row["strike"].iloc[0])
    opt_type = row["optionType"].iloc[0]

    # Fetch intraday underlying prices
    hist = yf.Ticker(underlying).history(period="1d", interval="5m")
    if hist.empty:
        raise HTTPException(404, "No intraday data")
    result = []
    for ts, price in hist["Close"].items():
        intrinsic = max((price - strike), 0) if opt_type=="call" else max((strike - price), 0)
        pnl = intrinsic - premium
        result.append(PnlPoint(timestamp=ts.isoformat(), pnl=float(pnl)))
    return result

