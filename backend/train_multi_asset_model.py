# train_multi_asset_model.py

"""
This module trains and saves models for asset class and strategy prediction.
Used during auto-retraining from feedback data.
"""

import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from pathlib import Path

def train_asset_and_strategy_model(feedback_path="feedback.csv"):
    """
    Trains multi-asset and strategy models from the feedback.csv file.
    Saves models and vectorizer to .joblib files.
    """
    # Load feedback CSV
    df = pd.read_csv(feedback_path)

    if "belief" not in df.columns or "label" not in df.columns:
        raise ValueError("feedback.csv must contain 'belief' and 'label' columns")

    # Basic preprocessing
    df["belief"] = df["belief"].astype(str).str.lower()
    df["label"] = df["label"].astype(str)

    # Initialize TF-IDF vectorizer
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=500)
    X = vectorizer.fit_transform(df["belief"])
    y = df["label"]

    # Train classifier
    clf = LogisticRegression()
    clf.fit(X, y)

    # Save models
    joblib.dump(clf, "multi_asset_model.joblib")
    joblib.dump(vectorizer, "multi_vectorizer.joblib")

    print("✅ Multi-asset models trained and saved.")

# Optional local test
if __name__ == "__main__":
    train_asset_and_strategy_model()
