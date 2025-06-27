# backend/feedback_trainer.py

"""
This module supports training and updating:
1. Feedback classification (good/bad) from belief + strategy
2. Strategy-type classification (from belief text to strategy type)
3. Appending simulated or real feedback to feedback_data.json
"""

import os
import json
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === Path Setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")
FEEDBACK_MODEL_PATH = os.path.join(BASE_DIR, "feedback_model.joblib")
FEEDBACK_VECTOR_PATH = os.path.join(BASE_DIR, "vectorizer.joblib")
STRATEGY_MODEL_PATH = os.path.join(BASE_DIR, "feedback_strategy_model.joblib")
STRATEGY_VECTOR_PATH = os.path.join(BASE_DIR, "feedback_strategy_vectorizer.joblib")

# === Load and clean feedback data ===
def load_feedback_data():
    with open(FEEDBACK_FILE, "r") as f:
        raw_data = json.load(f)

    cleaned = []
    for entry in raw_data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        result = entry.get("result") or entry.get("feedback")

        # Convert strategy dict to string for input vector
        strategy_text = json.dumps(strategy) if isinstance(strategy, dict) else str(strategy)

        if belief and strategy_text and result:
            cleaned.append({
                "text": f"{belief} => {strategy_text}",
                "label": 1 if result.lower() == "good" else 0
            })

    return pd.DataFrame(cleaned)

# === Train good vs bad feedback classifier ===
def train_feedback_model():
    df = load_feedback_data()
    if df.empty:
        print("❌ No valid feedback data found.")
        return

    X, y = df["text"], df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    vectorizer = TfidfVectorizer()
    classifier = LogisticRegression(max_iter=500)

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    classifier.fit(X_train_vec, y_train)
    y_pred = classifier.predict(X_test_vec)

    # Save model and vectorizer separately or as dict
    joblib.dump({"vectorizer": vectorizer, "classifier": classifier}, FEEDBACK_MODEL_PATH)
    print(f"✅ Saved feedback model to: {FEEDBACK_MODEL_PATH}")
    print("📊 Classification Report (Feedback Good vs Bad):")
    print(classification_report(y_test, y_pred))

# === Train belief-to-strategy-type model (supervised by feedback) ===
def train_strategy_classifier_from_feedback():
    with open(FEEDBACK_FILE, "r") as f:
        raw_data = json.load(f)

    records = []
    for entry in raw_data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        strategy_type = strategy.get("type") if isinstance(strategy, dict) else str(strategy)

        if belief and strategy_type:
            records.append({"belief": belief, "strategy_type": strategy_type})

    df = pd.DataFrame(records).dropna()

    if df.empty:
        print("❌ No valid strategy training data found.")
        return

    X = df["belief"]
    y = df["strategy_type"]

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_vec, y)

    joblib.dump(model, STRATEGY_MODEL_PATH)
    joblib.dump(vectorizer, STRATEGY_VECTOR_PATH)

    print("✅ Trained and saved feedback_strategy_model + vectorizer")

# === Append new feedback entry to feedback_data.json ===
def append_feedback_entry(belief, strategy, result):
    """
    Appends a feedback record for learning.

    Params:
    - belief (str): User belief input
    - strategy (dict): Generated strategy object
    - result (str): 'good' or 'bad'
    """
    entry = {
        "belief": belief,
        "strategy": strategy,
        "result": result
    }

    # Load existing data
    with open(FEEDBACK_FILE, "r") as f:
        existing = json.load(f)

    # Append and save
    existing.append(entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"📥 Appended feedback entry: {result.upper()} → {belief}")

# === Run both training routines directly from CLI ===
if __name__ == "__main__":
    train_feedback_model()
    train_strategy_classifier_from_feedback()
