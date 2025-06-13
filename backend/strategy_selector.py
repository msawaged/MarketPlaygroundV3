# strategy_selector.py
# Selects a base strategy based on predicted tags

from datetime import datetime, timedelta

def select_strategy(ticker, tags):
    """
    Generates a basic options strategy based on AI-inferred tags.
    
    Args:
        ticker (str): Detected ticker
        tags (dict): Predicted tags (direction, duration, volatility)

    Returns:
        dict: Base strategy output
    """
    direction = tags["direction"]
    duration = tags["duration"]
    vol = tags["volatility"]

    # Set expiry date logic
    today = datetime.today()
    if duration == "short":
        expiry = today + timedelta(days=7)
    elif duration == "medium":
        expiry = today + timedelta(days=30)
    else:
        expiry = today + timedelta(days=90)
    
    expiry_str = expiry.strftime("%Y-%m-%d")

    # Strategy type and legs
    if direction == "bullish":
        strategy = {
            "type": "Call Debit Spread (Live)",
            "legs": [f"Buy {ticker} ATM call", f"Sell {ticker} higher call"],
        }
    elif direction == "bearish":
        strategy = {
            "type": "Put Debit Spread (Live)",
            "legs": [f"Buy {ticker} ATM put", f"Sell {ticker} lower put"],
        }
    else:
        strategy = {
            "type": "Iron Condor (Live)",
            "legs": [
                f"Sell {ticker} lower put", f"Buy {ticker} even-lower put",
                f"Sell {ticker} higher call", f"Buy {ticker} even-higher call"
            ],
        }

    strategy["expiry"] = expiry_str
    strategy["payout"] = "2.0x"  # You can change this dynamically later

    return strategy
