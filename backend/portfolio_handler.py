# backend/portfolio_handler.py

"""
Delegates portfolio saving and retrieval to the logger module.
Also auto-executes high-confidence trades via Alpaca.
Logs real executions using trade_execution_logger.
"""

from backend.logger.portfolio_logger import log_trade, get_user_portfolio
from backend.alpaca_client import submit_market_buy
from backend.trade_execution_logger import log_execution  # ✅ New: logs Alpaca responses

def save_trade(user_id: str, belief: str, strategy: dict):
    """
    Saves a trade entry for the given user.
    Executes via Alpaca if confidence is high and logs execution.
    """
    trade_data = {
        "belief": belief,
        "strategy": strategy
    }

    # ✅ Log belief + strategy locally in portfolio history
    log_trade(user_id, trade_data)

    # 🚨 Auto-execute only high-confidence STOCK or OPTIONS trades
    confidence = strategy.get("confidence", 0)
    asset_class = strategy.get("asset_class", "").lower()
    ticker = strategy.get("ticker")
    qty = strategy.get("quantity", 1)

    if confidence >= 0.7 and ticker and asset_class in ["stock", "options"]:
        print(f"🚀 Executing trade via Alpaca: {ticker} x{qty} (confidence={confidence})")

        # ✅ Submit to Alpaca
        alpaca_response = submit_market_buy(ticker, qty)
        print(f"✅ Alpaca response: {alpaca_response}")

        # ✅ Log execution if successful
        if alpaca_response:
            log_execution(user_id, {
                "ticker": ticker,
                "quantity": qty,
                "order_id": alpaca_response.get("id"),
                "status": alpaca_response.get("status"),
                "filled_avg_price": alpaca_response.get("filled_avg_price")
            })

def get_portfolio(user_id: str):
    """
    Retrieves the full trade history (portfolio) for a given user.
    """
    return get_user_portfolio(user_id)
