# backend/strategy_selector.py
# 📊 Strategy selection based on direction, confidence, and market data

def select_strategy(direction: str, confidence: str, ticker: str, live_price: float, expiries: list) -> dict:
    """
    Picks a basic spread or directional option strategy based on market data.
    """
    try:
        price = round(live_price, 2)
        expiry = expiries[0] if expiries else "N/A"

        if direction == "bullish":
            return {
                "type": "Bull Call Spread",
                "legs": f"Buy {ticker} {price - 5}c / Sell {ticker} {price + 5}c",
                "expiry": expiry,
                "payout": "2x"
            }
        elif direction == "bearish":
            return {
                "type": "Bear Put Spread",
                "legs": f"Buy {ticker} {price + 5}p / Sell {ticker} {price - 5}p",
                "expiry": expiry,
                "payout": "1.8x"
            }
        else:
            return {
                "type": "Neutral Strategy",
                "legs": f"Sell {ticker} {price}c / Sell {ticker} {price}p",
                "expiry": expiry,
                "payout": "1.5x"
            }
    except Exception as e:
        print(f"[strategy_selector] ❌ Strategy selection error: {e}")
        return {
            "type": "Fallback",
            "legs": f"Buy {ticker} {price}c",
            "expiry": "N/A",
            "payout": "1x"
        }
