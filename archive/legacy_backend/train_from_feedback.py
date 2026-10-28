# backend/train_from_feedback.py

"""
Retrains the ML strategy model using accumulated GOOD feedback data.
The model learns to map user beliefs (plus risk profile) to recommended strategies.
"""

import os
import json
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from joblib import dump

# === File Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback_data.json")
MODEL_PATH = os.path.join(BASE_DIR, "ai_engine", "multi_asset_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "ai_engine", "multi_vectorizer.joblib")

# === Load JSON feedback and convert to DataFrame ===
def load_feedback_data():
    try:
        with open(FEEDBACK_PATH, "r") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception as e:
        print(f"❌ Error loading feedback data: {e}")
        return pd.DataFrame()

# === Main training function ===
def train_from_feedback():
    df = load_feedback_data()

    if df.empty:
        print("❌ No feedback data found or file is empty.")
        return

    # Filter for positive feedback only
    df = df[df["feedback"] == "good"]

    # Drop entries missing key fields
    df = df.dropna(subset=["belief", "strategy"])

    # Ensure 'risk_profile' column exists
    df["risk_profile"] = df.get("risk_profile", "moderate").fillna("moderate")

    if df.empty:
        print("❌ No usable GOOD feedback entries available.")
        return

    # Format input: belief + risk profile
    df["input_text"] = df["belief"] + " | risk: " + df["risk_profile"]
    X = df["input_text"]
    y = df["strategy"]

    # === Train TF-IDF + Logistic Regression ===
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    X_vec = vectorizer.fit_transform(X)

    model = LogisticRegression(max_iter=500)
    model.fit(X_vec, y)

    # === Optional: Performance Report ===
    X_train, X_test, y_train, y_test = train_test_split(X_vec, y, test_size=0.2, random_state=42, stratify=y)
    preds = model.predict(X_test)
    print("🧠 Updated Strategy Model Accuracy Report:\n")
    print(classification_report(y_test, preds))

    # === Save updated model and vectorizer ===
    dump(model, MODEL_PATH)
    dump(vectorizer, VECTORIZER_PATH)
    print(f"✅ Model saved to → {MODEL_PATH}")
    print(f"✅ Vectorizer saved to → {VECTORIZER_PATH}")

# === CLI Trigger ===
if __name__ == "__main__":
    train_from_feedback()
