# test_strategy_selector.py
from strategy_selector import suggest_strategy

# Simulated ML tags from the classifier
sample_tags = {
    "direction": "bullish",
    "duration": "short",
    "volatility": "high"
}

# Simulated detected ticker
sample_ticker = "TSLA"

# Run test
strategy = suggest_strategy(sample_tags, sample_ticker)

# Display output
print("🎯 Suggested Strategy:")
print(f"Type: {strategy['type']}")
print(f"Legs: {strategy['legs']}")
print(f"Expiry: {strategy['expiry']}")
print(f"Payout: {strategy['payout']}")
