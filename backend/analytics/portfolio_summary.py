"""
Generates portfolio summaries and chart visuals for users.
"""

import json
import os
import matplotlib.pyplot as plt
from fastapi.responses import FileResponse
from typing import Dict
from backend.portfolio_handler import get_portfolio


def summarize_user_portfolio(user_id: str) -> Dict:
    """
    Fetches user's portfolio and returns summary statistics.
    Handles both raw and JSON-stringified strategies.

    Args:
        user_id (str): The user ID whose portfolio to summarize

    Returns:
        Dict: Summary with total value, PnL, count, and average position
    """
    trades = get_portfolio(user_id)

    parsed_trades = []
    for t in trades:
        strategy = t.get("strategy", {})
        # Handle JSON string case
        if isinstance(strategy, str):
            try:
                strategy = json.loads(strategy)
            except json.JSONDecodeError:
                strategy = {}

        parsed_trades.append({
            "symbol": strategy.get("symbol"),
            "unrealized_pl": strategy.get("unrealized_pl", 0),
            "market_value": strategy.get("market_value", 0)
        })

    total_value = sum(t.get("market_value", 0) for t in parsed_trades)
    total_pnl = sum(t.get("unrealized_pl", 0) for t in parsed_trades)
    avg_position = total_value / len(parsed_trades) if parsed_trades else 0

    return {
        "user_id": user_id,
        "num_positions": len(parsed_trades),
        "total_market_value": round(total_value, 2),
        "total_unrealized_pnl": round(total_pnl, 2),
        "average_position_value": round(avg_position, 2)
    }


def generate_portfolio_chart(user_id: str) -> FileResponse:
    """
    Generates a bar chart showing unrealized PnL by symbol.

    Args:
        user_id (str): User ID to fetch and chart portfolio for

    Returns:
        FileResponse: PNG image of the chart
    """
    trades = get_portfolio(user_id)

    parsed_trades = []
    for t in trades:
        strategy = t.get("strategy", {})
        if isinstance(strategy, str):
            try:
                strategy = json.loads(strategy)
            except json.JSONDecodeError:
                strategy = {}
        parsed_trades.append({
            "symbol": strategy.get("symbol", "N/A"),
            "unrealized_pl": strategy.get("unrealized_pl", 0)
        })

    symbols = [t["symbol"] for t in parsed_trades]
    pnls = [t["unrealized_pl"] for t in parsed_trades]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(symbols, pnls)
    plt.title("Unrealized PnL by Position")
    plt.xlabel("Ticker Symbol")
    plt.ylabel("Unrealized PnL ($)")
    plt.xticks(rotation=45)
    plt.tight_layout()

    image_path = "portfolio_chart.png"
    plt.savefig(image_path)
    plt.close()

    return FileResponse(image_path, media_type="image/png", filename=image_path)
