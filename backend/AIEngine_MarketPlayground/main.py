#!/usr/bin/env python3
"""
main.py

MarketPlayground AI Engine end-to-end:
1) Prompt for your market belief & get an AI-suggested strategy
2) Score every option in your sector by (volume × leverage)
3) Pick the top-scoring contract as “best strategy”
4) Plot the payoff at expiry
5) Plot the intraday P/L curve
"""

from ai_engine import process_prompt
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# ── CONFIG: sector tickers to scan ─────────────────────────────────
SECTOR_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]


def fetch_and_score():
    """
    Fetch all calls & puts for each ticker in SECTOR_TICKERS,
    compute a rough “leverage” = (IV × spot) / mid_price,
    and score = volume × leverage.
    Returns a DataFrame sorted by descending score.
    """
    all_dfs = []

    for sym in SECTOR_TICKERS:
        print(f"--- Fetching {sym} ---")
        tkr = yf.Ticker(sym)

        # get today's last close as spot price
        hist = tkr.history(period="1d")
        if hist.empty:
            print(f"  ⚠️  No underlying data for {sym}")
            continue
        spot = hist["Close"].iloc[-1]

        # iterate all expirations
        for exp in tkr.options:
            try:
                chain = tkr.option_chain(exp)
            except Exception:
                continue

            for opt_df, opt_type in [(chain.calls, "call"), (chain.puts, "put")]:
                df = opt_df.copy()
                if df.empty:
                    continue

                # annotate
                df["underlying"]  = sym
                df["expiry"]      = exp
                df["optionType"]  = opt_type

                # mid-price & filter
                df["mid_price"] = (df["bid"] + df["ask"]) / 2
                df = df[df["mid_price"] > 0]

                # leverage & score
                df["leverage"] = (df["impliedVolatility"].fillna(0) * spot) / df["mid_price"]
                df["score"]    = df["volume"].fillna(0) * df["leverage"]

                all_dfs.append(df[[
                    "underlying",
                    "contractSymbol",
                    "expiry",
                    "strike",
                    "optionType",
                    "volume",
                    "impliedVolatility",
                    "mid_price",
                    "leverage",
                    "score",
                ]])

    if not all_dfs:
        return pd.DataFrame()

    master = pd.concat(all_dfs, ignore_index=True)
    return master.sort_values("score", ascending=False)


def plot_expiry_payoff(best, spot):
    """
    Plot intrinsic payoff minus premium at expiry for the chosen contract.
    """
    strike   = best.strike
    opt_type = best.optionType
    premium  = best.mid_price
    label    = f"{best.contractSymbol} Expiry P/L"

    prices = [spot + i for i in range(-30, 31)]
    payoff = []
    for p in prices:
        intrinsic = max((p - strike) if opt_type == "call" else (strike - p), 0)
        payoff.append(intrinsic - premium)

    plt.figure(figsize=(10, 5))
    plt.plot(prices, payoff, label=label, linewidth=2)
    plt.axvline(spot, linestyle="--", label="Current Price")
    plt.title(label)
    plt.xlabel("Price at Expiry")
    plt.ylabel("P/L ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()


def plot_intraday_pnl(best):
    """
    Plot P/L over today's 5-minute bars, using intrinsic value minus premium.
    """
    sym      = best.underlying
    strike   = best.strike
    opt_type = best.optionType
    premium  = best.mid_price
    label    = f"{best.contractSymbol} Intraday P/L"

    hist = yf.Ticker(sym).history(period="1d", interval="5m")
    if hist.empty:
        print(f"⚠️  No intraday data for {sym}")
        return

    prices = hist["Close"]
    pnl    = [
        max((p - strike) if opt_type == "call" else (strike - p), 0) - premium
        for p in prices
    ]

    plt.figure(figsize=(10, 5))
    plt.plot(prices.index, pnl, label=label, linewidth=2)
    plt.axhline(0, linestyle="--", label="Breakeven")
    plt.title(label)
    plt.xlabel("Time")
    plt.ylabel("P/L ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()


def main():
    # ── Step 1: Ask AI for a strategy suggestion ──────────────────────
    print("Welcome to MarketPlayground AI Engine 🧠")
    user_input = input("Enter your market belief: ")
    result = process_prompt(user_input)

    print("\nAI-Suggested Strategy:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # ── Step 2: Score all options by volume × leverage ──────────────
    print("\nScoring options based on volume × leverage…")
    df = fetch_and_score()
    if df.empty:
        print("❌ No options fetched.")
        return

    # ── Step 3: Select the top-scoring contract ────────────────────
    best = df.iloc[0]
    print("\nBest high-vol, high-leverage pick:")
    print(f"  Underlying: {best.underlying}")
    print(f"  Contract:   {best.contractSymbol}")
    print(f"  Expiry:     {best.expiry}")
    print(f"  Strike:     {best.strike}")
    print(f"  Type:       {best.optionType}")
    print(f"  Premium:    ${best.mid_price:.2f}")
    print(f"  Score:      {best.score:.1f}")

    # ── Step 4: Plot the expiry payoff curve ───────────────────────
    spot = yf.Ticker(best.underlying).history(period="1d")["Close"].iloc[-1]
    plot_expiry_payoff(best, spot)

    # ── Step 5: Plot intraday P/L movement ────────────────────────
    plot_intraday_pnl(best)

    # Show both charts
    plt.show()


if __name__ == "__main__":
    main()
