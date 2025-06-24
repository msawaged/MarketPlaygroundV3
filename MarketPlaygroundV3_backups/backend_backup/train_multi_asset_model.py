# train_multi_asset_model.py

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

def train_multi_asset_model():
    """
    Trains a multi-asset classifier from feedback.csv using 'belief' → 'asset_class'.
    Saves the model and vectorizer.
    """
    df = pd.read_csv("feedback.csv")

    if "belief" not in df.columns or "asset_class" not in df.columns:
        raise ValueError("feedback.csv must contain 'belief' and 'asset_class' columns.")

    X = df["belief"].astype(str)
    y = df["asset_class"].astype(str)

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_vec, y)

    joblib.dump(model, "multi_asset_model.joblib")
    joblib.dump(vectorizer, "multi_vectorizer.joblib")
    print("✅ Multi-asset model trained and saved.")

# Optional: run directly for testing
if __name__ == "__main__":
    train_multi_asset_model()
