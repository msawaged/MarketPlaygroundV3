# app.py

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from joblib import load
import pandas as pd
import yfinance as yf

app = FastAPI()

# Load the trained pipeline once at startup
try:
    model = load("best_model.joblib")  # This is the full preprocessing + RF pipeline
    print("Loaded trained model from best_model.joblib")
except Exception as e:
    print(f"ERROR: Could not load best_model.joblib: {e}")
    model = None

class BeliefRequest(BaseModel):
    """
    Incoming JSON structure for /strategy.
    Example:
        { "belief": "TSLA will rally today" }
    """
    belief: str

@app.post("/strategy")
def strategy(req: BeliefRequest):
    """
    Given a market belief (string), decide on candidate contracts, compute features for each,
    and predict realized P/L using the loaded pipeline.
    """
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    # ------------------------------------------------------------
    # STEP A: Parse the belief into candidate option(s).
    # For this example, we'll hard-code one candidate. Replace this
    # with your own logic to derive a list of candidates.
    # Candidate dictionary keys: symbol, contractSymbol, optionType,
    # strike, expiry, labelDate.
    # ------------------------------------------------------------
    example_candidate = {
        "symbol": "TSLA",
        "contractSymbol": "TSLA250606C01200000",
        "optionType": "call",
        "strike": 1200.0,
        "expiry": "2025-06-06",
        "labelDate": pd.Timestamp.now().date().isoformat()
    }
    candidates = [example_candidate]

    # ------------------------------------------------------------
    # STEP B: For each candidate, fetch option chain row and compute features:
    #   impliedVolatility, volume, mid_price, strike, openInterest,
    #   underlyingReturn, assetType
    # ------------------------------------------------------------
    rows = []
    for cand in candidates:
        symbol = cand["symbol"]
        contract = cand["contractSymbol"]
        optionType = cand["optionType"]
        strike_price = cand["strike"]
        expiry = cand["expiry"]
        labelDate = cand["labelDate"]

        # 1) Fetch the option chain for this expiry
        tkr = yf.Ticker(symbol)
        try:
            chain = tkr.option_chain(expiry)
        except Exception:
            continue  # skip if chain unavailable

        df_chain = chain.calls if optionType == "call" else chain.puts
        if df_chain.empty:
            continue

        # 2) Find the exact row for this contractSymbol
        try:
            row = df_chain[df_chain["contractSymbol"] == contract].iloc[0]
        except IndexError:
            continue  # contract not found

        # 3) Extract features
        impliedVol = row["impliedVolatility"]
        volume = row["volume"]
        mid_price = (row["bid"] + row["ask"]) / 2
        openInterest = row["openInterest"]
        strike_val = row["strike"]

        # 4) Compute underlyingReturn (same as in collect_labels.py)
        try:
            hist = tkr.history(start=labelDate, end=expiry)
        except Exception:
            continue
        if hist.empty:
            continue
        try:
            price_label = hist.loc[labelDate]["Close"]
        except KeyError:
            price_label = hist["Close"].iloc[0]
        try:
            price_expiry = hist.loc[expiry]["Close"]
        except KeyError:
            price_expiry = hist["Close"].iloc[-1]
        if price_label == 0:
            continue
        underlyingReturn = (price_expiry / price_label) - 1

        # 5) assetType is just the symbol
        assetType = symbol

        # 6) Build a feature dictionary
        feature_dict = {
            "impliedVolatility": impliedVol,
            "volume": volume,
            "mid_price": mid_price,
            "strike": strike_val,
            "openInterest": openInterest,
            "underlyingReturn": underlyingReturn,
            "assetType": assetType
        }
        rows.append(feature_dict)

    if not rows:
        raise HTTPException(status_code=404, detail="No valid candidates found")

    df_features = pd.DataFrame(rows)

    # ------------------------------------------------------------
    # STEP C: Use the pipeline to predict realizedPL for each row
    # ------------------------------------------------------------
    try:
        preds = model.predict(df_features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

    # ------------------------------------------------------------
    # STEP D: Build the response combining contractSymbol + predictedPL
    # ------------------------------------------------------------
    response = []
    for cand, pred in zip(candidates, preds):
        response.append({
            "contractSymbol": cand["contractSymbol"],
            "predictedPL": float(pred)
        })

    return {"suggestions": response}

if __name__ == "__main__":
    # To run directly: python app.py
    uvicorn.run("app:app", host="0.0.0.0", port=8001)
