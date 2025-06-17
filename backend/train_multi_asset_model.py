# train_multi_asset_model.py
# This script trains a classifier to map beliefs to strategies across multiple asset types.

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from joblib import dump

# Sample multi-asset belief-strategy training data
data = [
    {"belief": "I think NVDA will rise", "strategy": "Buy Call Option", "asset": "Options"},
    {"belief": "TSLA will drop next week", "strategy": "Buy Put Option", "asset": "Options"},
    {"belief": "I want stable income", "strategy": "Buy Treasury Bonds", "asset": "Bonds"},
    {"belief": "The US dollar is falling", "strategy": "Short UUP", "asset": "ETF"},
    {"belief": "Bitcoin is going to explode", "strategy": "Long BTC", "asset": "Crypto"},
    {"belief": "I expect QQQ to crash", "strategy": "Buy QQQ Puts", "asset": "Options"},
    {"belief": "The market is bullish", "strategy": "Buy SPY", "asset": "ETF"},
    {"belief": "Gold is a safe bet now", "strategy": "Buy GLD", "asset": "ETF"},
]

df = pd.DataFrame(data)

# Step 1: Vectorize beliefs
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(df["belief"])

# Step 2: Train strategy model
strategy_model = LogisticRegression()
strategy_model.fit(X, df["strategy"])

# Step 3: Train asset type model
asset_model = LogisticRegression()
asset_model.fit(X, df["asset"])

# Save models
dump(vectorizer, "multi_vectorizer.joblib")
dump(strategy_model, "multi_strategy_model.joblib")
dump(asset_model, "multi_asset_model.joblib")

print("✅ Multi-asset models trained and saved.")
