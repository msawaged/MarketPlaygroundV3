# backend/strategy_outcome_summary.py

import pandas as pd
import os

# 📍 CSV path from logger
OUTCOME_LOG = os.path.join(os.path.dirname(__file__), "strategy_outcomes.csv")


def load_outcome_data():
    if not os.path.exists(OUTCOME_LOG):
        raise FileNotFoundError("❌ strategy_outcomes.csv not found — no data to summarize.")
    return pd.read_csv(OUTCOME_LOG)


def summarize_outcomes():
    df = load_outcome_data()
    if df.empty:
        return {"message": "No outcomes recorded yet."}

    summary = {}

    # 🎯 Overall stats
    summary["total_records"] = len(df)
    summary["avg_pnl"] = round(df["pnl_percent"].mean(), 2)
    summary["win_rate"] = round((df["result"] == "win").mean() * 100, 2)
    summary["loss_rate"] = round((df["result"] == "loss").mean() * 100, 2)

    # 🥇 Top strategies by average PnL
    top_strategies = (
        df.groupby("strategy")["pnl_percent"]
        .mean()
        .sort_values(ascending=False)
        .head(5)
        .round(2)
        .to_dict()
    )
    summary["top_strategies"] = top_strategies

    # 📈 Most used tickers
    top_tickers = df["ticker"].value_counts().head(5).to_dict()
    summary["top_tickers"] = top_tickers

    return summary


# 🧪 Local test block
if __name__ == "__main__":
    stats = summarize_outcomes()
    print("\n📊 Strategy Outcome Summary:")
    for k, v in stats.items():
        print(f"{k}: {v}")
