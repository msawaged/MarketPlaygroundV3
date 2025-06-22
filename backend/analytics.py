# backend/analytics.py

from backend.portfolio_handler import get_portfolio
from backend.feedback_handler import load_feedback_model

def summarize_user_portfolio(user_id: str):
    trades = get_portfolio(user_id)
    summary = {
        "total_trades": len(trades),
        "good_feedback": 0,
        "bad_feedback": 0,
        "unknown": 0
    }

    model = load_feedback_model()

    for trade in trades:
        belief = trade.get("belief", "")
        strategy = trade.get("strategy", "")
        result = trade.get("result", "")

        # Try to re-score if no explicit feedback
        if not result and model:
            text = f"{belief} => {strategy}"
            clf = model["classifier"]
            vec = model["vectorizer"]
            pred = clf.predict(vec.transform([text]))[0]
            result = "good" if pred == 1 else "bad"

        # Count feedback
        if result == "good":
            summary["good_feedback"] += 1
        elif result == "bad":
            summary["bad_feedback"] += 1
        else:
            summary["unknown"] += 1

    return summary

# === [ADD THIS AT THE BOTTOM OF backend/analytics.py] ===

import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse

def generate_portfolio_chart(user_id: str):
    """
    Generate a basic chart showing number of trades over time for the user.
    Returns: StreamingResponse with PNG image.
    """
    from backend.portfolio_handler import get_portfolio

    portfolio = get_portfolio(user_id)

    if not portfolio:
        raise ValueError("No portfolio data found.")

    # Convert timestamps to datetime and group by date
    df = pd.DataFrame(portfolio)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    volume_by_day = df.groupby("date").size()

    # Plot the chart
    plt.figure(figsize=(8, 4))
    plt.plot(volume_by_day.index, volume_by_day.values, marker="o")
    plt.title(f"📈 Trade Volume Over Time — {user_id}")
    plt.xlabel("Date")
    plt.ylabel("Trades")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Output to BytesIO for FastAPI StreamingResponse
    img_io = BytesIO()
    plt.savefig(img_io, format="png")
    img_io.seek(0)

    return StreamingResponse(content=img_io, media_type="image/png")
