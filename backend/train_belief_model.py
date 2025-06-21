# train_belief_model.py
# ✅ Trains the belief model for interpreting user beliefs into sentiment tags

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

# ✅ 1. Load training data
data = pd.DataFrame({
    "belief": [
        "I think AAPL will go up",
        "TSLA is going to crash",
        "The market is looking stable",
        "NVDA will fly next week",
        "I feel like SPY might dip soon",
        "QQQ to the moon!",
        "Interest rates will hurt TLT",
        "Bitcoin is dead",
        "I'm bearish on bonds",
        "Energy stocks are on the rise"
    ],
    "label": [
        "bullish",
        "bearish",
        "neutral",
        "bullish",
        "bearish",
        "bullish",
        "bearish",
        "bearish",
        "bearish",
        "bullish"
    ]
})

# ✅ 2. Transform belief text using TF-IDF
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(data["belief"])
y = data["label"]

# ✅ 3. Train RandomForestClassifier
model = RandomForestClassifier()
model.fit(X, y)

# ✅ 4. Save both the model and vectorizer
save_dir = os.path.dirname(os.path.abspath(__file__))

joblib.dump(model, os.path.join(os.path.dirname(__file__), "belief_model.joblib"))
joblib.dump(vectorizer, os.path.join(os.path.dirname(__file__), "belief_vectorizer.joblib"))

print("✅ Belief model and vectorizer saved successfully.")
