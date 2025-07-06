# backend/strategy_outcome_summary.py

"""
📊 Summarizes logged strategy outcomes from strategy_outcomes.csv.
Safely handles missing files or columns.
"""

import os
import pandas as pd
from collections import defaultdict

def summarize_strategy_outcomes():
    csv_path = os.path.join("backend", "logs", "strategy_outcomes.csv")

    if not os.path.exists(csv_path):
        return {"message": "No outcomes logged yet."}

    try:
        df = pd.read_csv(csv_path)

        if df.empty:
            return {"message": "No strategy outcomes available."}

        # Handle missing 'pnl' column gracefully
        has_pnl = "pnl" in df.columns
        has_result = "result" in df.columns
        has_type = "strategy_type" in df.columns

        total_entries = len(df)
        avg_pnl = df["pnl"].mean() if has_pnl else "N/A"

        # Win/Loss Calculation
        if has_result:
            win_rate = round((df["result"] == "win").sum() / total_entries, 2)
        else:
            win_rate = "N/A"

        # Strategy Breakdown
        breakdown_by_type = defaultdict(dict)
        if has_type and has_result:
            for strategy in df["strategy_type"].unique():
                subset = df[df["strategy_type"] == strategy]
                breakdown_by_type[strategy] = {
                    "count": len(subset),
                    "win_rate": round((subset["result"] == "win").sum() / len(subset), 2) if len(subset) > 0 else 0.0
                }

        return {
            "total_entries": total_entries,
            "average_pnl": avg_pnl,
            "win_rate": win_rate,
            "breakdown_by_type": breakdown_by_type
        }

    except Exception as e:
        return {"error": f"Failed to summarize outcomes: {str(e)}"}
