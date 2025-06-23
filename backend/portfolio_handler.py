# backend/portfolio_handler.py

"""
Delegates portfolio saving and retrieval to the logger module.
This provides a clean interface for the rest of the backend.
"""

from backend.logger.portfolio_logger import log_trade, get_user_portfolio

def save_trade(user_id: str, belief: str, strategy: dict):
    """
    Saves a trade entry for the given user.
    """
    trade_data = {
        "belief": belief,
        "strategy": strategy
    }
    log_trade(user_id, trade_data)

def get_portfolio(user_id: str):
    """
    Retrieves the full trade history (portfolio) for a given user.
    """
    return get_user_portfolio(user_id)
