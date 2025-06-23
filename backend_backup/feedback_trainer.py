# backend/feedback_trainer.py

import json
import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === Path setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")
MODEL_FILE = os.path.join(BASE_DIR, "feedback_model.joblib")

# === Load and clean data ===
def load_feedback_data():
    with open(FEEDBACK_FILE, "r") as f:
        raw_data = json.load(f)

    cleaned = []
    for entry in raw_data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        result = entry.get("result") or entry.get("feedback")  # ✅ Check both keys

        if isinstance(strategy, dict):
            strategy_text = json.dumps(strategy)
        else:
            strategy_text = str(strategy)

        if belief and result and strategy_text:
            cleaned.append({
                "text": f"{belief} => {strategy_text}",
                "label": 1 if result.lower() == "good" else 0
            })

    return pd.DataFrame(cleaned)

# === Train + Save model ===
def train_model():
    df = load_feedback_data()

    if df.empty:
        print("❌ No valid data found.")
        return

    print("✅ Training data sample:")
    print(df.head())

    X, y = df["text"], df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    vectorizer = TfidfVectorizer()
    clf = LogisticRegression()

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf.fit(X_train_vec, y_train)
    print("✅ Model trained.")

    y_pred = clf.predict(X_test_vec)
    print("📊 Classification Report:")
    print(classification_report(y_test, y_pred))

    # ✅ Save as dict for feedback_handler compatibility
    model_dict = {
        "vectorizer": vectorizer,
        "classifier": clf
    }

    joblib.dump(model_dict, MODEL_FILE)
    print(f"✅ Model saved to {MODEL_FILE}")

if __name__ == "__main__":
    train_model()
