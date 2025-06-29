# backend/fix_training_csv.py

import pandas as pd
import re

# Load your existing CSV
df = pd.read_csv("backend/Training_Strategies.csv")

# Function to extract ticker (assumes ticker is uppercase in belief)
def extract_ticker(belief):
    tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "GOOGL", "META", "SPY", "QQQ"]  # add more as needed
    for t in tickers:
        if t in belief.upper():
            return t
    return "AAPL"  # default fallback

# Function to infer direction from belief text
def infer_direction(belief):
    belief = belief.lower()
    if any(w in belief for w in ["go up", "rise", "bullish", "climb", "increase", "explode"]):
        return "bullish"
    elif any(w in belief for w in ["drop", "bearish", "fall", "decline", "crash"]):
        return "bearish"
    else:
        return "neutral"

# Apply the functions
df["ticker"] = df["belief"].apply(extract_ticker)
df["direction"] = df["belief"].apply(infer_direction)

# Save the updated CSV
df.to_csv("backend/Training_Strategies.csv", index=False)
print("✅ Training_Strategies.csv updated with ticker and direction.")
