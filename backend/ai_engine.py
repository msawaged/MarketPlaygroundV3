# ai_engine.py
# This is the core logic that turns user beliefs into tradable strategies using ML.

from belief_parser import detect_ticker, clean_belief
from belief_model import predict_tags
from strategy_selector import suggest_strategy

def run_ai_engine(belief: str):
    """
    Parses a user's belief, detects sentiment tags, and suggests a strategy.
    
    Input:
        belief (str): Natural language statement like "TSLA will go up next week"
    Output:
        Tuple:
            - parsed_result: dict with input, detected ticker, sentiment, and tags
            - strategy: dict with strategy details (type, legs, expiry, payout)
    """
    # Clean and extract info
    belief_cleaned = clean_belief(belief)
    ticker = detect_ticker(belief_cleaned)

    # Predict direction, duration, volatility using ML model
    tags = predict_tags(belief_cleaned)

    # Determine simplified sentiment (for fallback handling)
    sentiment = tags.get("direction", "neutral")

    # Package interpretation
    parsed_result = {
        "input": belief,
        "ticker": ticker,
        "sentiment": sentiment,
        "tags": tags,
    }

    # Suggest a strategy based on tags
    strategy = suggest_strategy(ticker, tags)

    return parsed_result, strategy
