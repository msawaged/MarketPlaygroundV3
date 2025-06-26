# backend/feedback_trainer.py

"""
This module supports training and updating:
1. Feedback classification (good/bad) from belief + strategy
2. Strategy-type classification (from belief text to strategy type)
3. Appending simulated or real feedback to feedback_data.json
"""

import json
import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")
MODEL_FILE = os.path.join(BASE_DIR, "feedback_model.joblib")
VECTORIZER_FILE = os.path.join(BASE_DIR, "vectorizer.joblib")


# === Load and clean feedback (good/bad) data ===
def load_feedback_data():
    with open(FEEDBACK_FILE, "r") as f:
        raw_data = json.load(f)

    cleaned = []
    for entry in raw_data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        result = entry.get("result") or entry.get("feedback")

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


# === Train Feedback Model (good vs bad) ===
def train_feedback_model():
    df = load_feedback_data()
    if df.empty:
        print("❌ No valid feedback data found.")
        return

    X, y = df["text"], df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    vectorizer = TfidfVectorizer()
    clf = LogisticRegression()

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf.fit(X_train_vec, y_train)
    y_pred = clf.predict(X_test_vec)

    model_dict = {
        "vectorizer": vectorizer,
        "classifier": clf
    }

    joblib.dump(model_dict, MODEL_FILE)
    print(f"✅ feedback_model.joblib saved. Accuracy:")
    print(classification_report(y_test, y_pred))


# === Train Strategy Classifier (belief → strategy_type) ===
def train_strategy_classifier_from_feedback():
    with open(FEEDBACK_FILE, "r") as f:
        raw_data = json.load(f)

    records = []
    for entry in raw_data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        if isinstance(strategy, dict):
            strategy_type = strategy.get("type")
        else:
            strategy_type = str(strategy)

        if belief and strategy_type:
            records.append({"belief": belief, "strategy_type": strategy_type})

    df = pd.DataFrame(records)
    df = df[df["strategy_type"].notnull()]

    if df.empty:
        print("❌ No valid strategy training data found.")
        return

    X = df["belief"]
    y = df["strategy_type"]

    vec = TfidfVectorizer()
    X_vec = vec.fit_transform(X)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_vec, y)

    joblib.dump(model, os.path.join(BASE_DIR, "feedback_strategy_model.joblib"))
    joblib.dump(vec, os.path.join(BASE_DIR, "feedback_strategy_vectorizer.joblib"))
    print("✅ Trained and saved feedback_strategy_model + vectorizer")


# === Append a new feedback entry ===
def append_feedback_entry(belief, strategy, result):
    """
    Appends a single feedback entry to feedback_data.json.

    Params:
    - belief (str): the original belief text
    - strategy (dict): result from AI engine (or simulated)
    - result (str): "good" or "bad" label
    """
    entry = {
        "belief": belief,
        "strategy": strategy,
        "result": result
    }

    # Load existing data
    with open(FEEDBACK_FILE, "r") as f:
        existing = json.load(f)

    # Append new entry
    existing.append(entry)

    # Write back
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"📥 Appended feedback entry: {result.upper()} for belief → {belief}")


# === Run both models if script is called directly ===
if __name__ == "__main__":
    train_feedback_model()
    train_strategy_classifier_from_feedback()
