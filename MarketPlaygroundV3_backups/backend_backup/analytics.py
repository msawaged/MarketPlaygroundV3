# backend/analytics.py

import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse

from backend.portfolio_handler import get_portfolio
from backend.feedback_handler import load_feedback_model


def summarize_user_portfolio(user_id: str):
    """
    Summarizes the user's portfolio:
    - Total number of trades
    - Count of 'good', 'bad', and 'unknown' feedback
    Uses feedback model to predict missing labels.
    """
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

        # Use model to re-score if result is missing
        if not result and model:
            text = f"{belief} => {strategy}"
            clf = model["classifier"]
            vec = model["vectorizer"]
            pred = clf.predict(vec.transform([text]))[0]
            result = "good" if pred == 1 else "bad"

        # Tally the feedback
        if result == "good":
            summary["good_feedback"] += 1
        elif result == "bad":
            summary["bad_feedback"] += 1
        else:
            summary["unknown"] += 1

    return summary


def generate_portfolio_chart(user_id: str):
    """
    Generate a basic chart showing number of trades over time for the user.
    Returns a StreamingResponse with PNG chart.
    """
    portfolio = get_portfolio(user_id)

    if not portfolio:
        raise ValueError("No portfolio data found.")

    # Convert portfolio to DataFrame and parse timestamps
    df = pd.DataFrame(portfolio)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date

    # Group by day and count trades
    volume_by_day = df.groupby("date").size()

    # Create the chart
    plt.figure(figsize=(8, 4))
    plt.plot(volume_by_day.index, volume_by_day.values, marker="o", linestyle="-")
    plt.title(f"Trade Volume Over Time — {user_id}")
    plt.xlabel("Date")
    plt.ylabel("Trades")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()

    # Output to a BytesIO stream for FastAPI StreamingResponse
    img_io = BytesIO()
    plt.savefig(img_io, format="png")
    img_io.seek(0)

    return StreamingResponse(content=img_io, media_type="image/png")
