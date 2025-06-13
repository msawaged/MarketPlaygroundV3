# ai_engine.py
# Main function to parse user belief and produce a base strategy

from belief_parser import detect_ticker
from belief_model import predict_tags  # You already have this from the trained ML model
from strategy_selector import select_strategy

def run_ai_engine(belief_text):
    """
    Parses user belief and returns a base strategy suggestion.
    
    Args:
        belief_text (str): Natural-language input from user
    
    Returns:
        dict: Parsed belief + strategy info
    """
    ticker = detect_ticker(belief_text)
    tags = predict_tags(belief_text)
    
    output = {
        "input": belief_text,
        "ticker": ticker,
        "sentiment": tags["direction"],
        "tags": tags
    }

    strategy = select_strategy(ticker, tags)
    return output, strategy
