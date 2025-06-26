# backend/train_from_feedback.py

"""
Retrains strategy model using accumulated feedback data.
Uses strategy name as label and belief text as input, then saves updated model.
"""

import os
import json
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from joblib import dump
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === Path Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback_data.json")
MODEL_PATH = os.path.join(BASE_DIR, "ai_engine", "multi_asset_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "ai_engine", "multi_vectorizer.joblib")

# === Load Feedback Data ===
def load_feedback_data():
    with open(FEEDBACK_PATH, "r") as f:
        data = json.load(f)
    return pd.DataFrame(data)

# === Preprocess and Train ===
def train_from_feedback():
    df = load_feedback_data()

    # Filter only GOOD feedback
    df = df[df["feedback"] == "good"]

    # Drop rows with missing belief or strategy
    df = df.dropna(subset=["belief", "strategy"])

    # Fill in missing risk_profile if not present
    if "risk_profile" not in df.columns:
        df["risk_profile"] = "moderate"
    else:
        df["risk_profile"] = df["risk_profile"].fillna("moderate")

    if df.empty:
        print("❌ No usable feedback entries found.")
        return

    # Combine belief + risk profile for training input
    df["input_text"] = df["belief"] + " | risk: " + df["risk_profile"]

    X = df["input_text"]
    y = df["strategy"]

    # Vectorize and Train
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    X_vec = vectorizer.fit_transform(X)

    model = LogisticRegression(max_iter=500)
    model.fit(X_vec, y)

    # Optional: Accuracy report
    X_train, X_test, y_train, y_test = train_test_split(X_vec, y, test_size=0.2, random_state=42)
    preds = model.predict(X_test)
    print("🧠 Updated Strategy Model Accuracy Report:\n")
    print(classification_report(y_test, preds))

    # Save model + vectorizer
    dump(model, MODEL_PATH)
    dump(vectorizer, VECTORIZER_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")
    print(f"✅ Vectorizer saved to {VECTORIZER_PATH}")

# === Triggerable from CLI
if __name__ == "__main__":
    train_from_feedback()
