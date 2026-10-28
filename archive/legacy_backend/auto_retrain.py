# backend/auto_retrain.py

"""
Auto-retrainer script to monitor feedback_data.json and retrain the strategy model if new examples are added.
Run this script in the background or on a loop (e.g. via train_loop.sh).
"""

import json
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
import joblib
from datetime import datetime

FEEDBACK_PATH = os.path.join("backend", "feedback_data.json")
MODEL_PATH = os.path.join("backend", "ai_engine", "multi_asset_model.joblib")
VEC_PATH = os.path.join("backend", "ai_engine", "multi_vectorizer.joblib")
COUNT_PATH = os.path.join("backend", "feedback_count.txt")

def get_existing_count():
    if os.path.exists(COUNT_PATH):
        with open(COUNT_PATH, "r") as f:
            return int(f.read().strip())
    return 0

def save_new_count(count):
    with open(COUNT_PATH, "w") as f:
        f.write(str(count))

def load_feedback():
    with open(FEEDBACK_PATH, "r") as f:
        data = json.load(f)
    return data

def train_model_from_feedback(data):
    df = pd.DataFrame(data)
    df = df.dropna(subset=["belief", "strategy"])
    X = df["belief"]
    y = df["strategy"]

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = LogisticRegression(max_iter=2000)
    model.fit(X_vec, y)

    y_pred = model.predict(X_vec)
    print("\n🧠 Auto-Retrain Model Accuracy Report:\n")
    print(classification_report(y, y_pred))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VEC_PATH)

    print(f"✅ Model saved to {MODEL_PATH}")
    print(f"✅ Vectorizer saved to {VEC_PATH}")

def main():
    try:
        feedback_data = load_feedback()
        current_count = len(feedback_data)
        last_count = get_existing_count()

        print(f"🧠 Feedback entries: {current_count} (previous: {last_count})")

        if current_count > last_count:
            print("🔄 New feedback detected — retraining model...")
            train_model_from_feedback(feedback_data)
            save_new_count(current_count)
        else:
            print("✅ No new feedback — skipping retraining.")

    except Exception as e:
        print(f"❌ Error during retraining: {e}")

if __name__ == "__main__":
    main()
