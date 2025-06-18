# backend/train_from_feedback.py

import json
import os
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

# Base directory of the project (adjust if needed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to the feedback data JSON file
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")

def load_feedback_data():
    """
    Loads feedback data from the JSON file and separates it into input texts and labels.
    Returns:
        texts: list of stringified (belief + strategy) inputs
        labels: list of user feedback ("good", "bad", etc.)
    """
    with open(FEEDBACK_FILE, "r") as f:
        data = json.load(f)

    texts = []
    labels = []

    for entry in data:
        belief = entry.get("belief", "")
        strategy = entry.get("strategy", {})
        strategy_desc = strategy.get("description", "")
        feedback = entry.get("feedback", "")

        # Combine belief and strategy into a single input string
        full_text = f"{belief} -> {strategy_desc}"
        texts.append(full_text)
        labels.append(feedback)

    return texts, labels

def train_feedback_model(texts, labels):
    """
    Trains a simple feedback classifier using TF-IDF and logistic regression.
    Returns:
        trained sklearn pipeline model
    """
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", LogisticRegression())
    ])
    pipeline.fit(texts, labels)
    return pipeline

def main():
    print("[train_from_feedback] Loading feedback data...")
    texts, labels = load_feedback_data()

    if len(set(labels)) < 2:
        print("[train_from_feedback] ❌ Not enough class diversity to train.")
        return

    if len(texts) < 5:
        # If fewer than 5 examples, train on everything
        print("[train_from_feedback] ⚠️ Not enough data for test split. Training on all data...")
        model = train_feedback_model(texts, labels)
    else:
        # Perform train/test split with stratification to preserve class balance
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, stratify=labels
        )
        model = train_feedback_model(X_train, y_train)

        # Optional performance report
        y_pred = model.predict(X_test)
        print(f"[train_from_feedback] ✅ Accuracy on test set: {accuracy_score(y_test, y_pred):.2f}")

    # Save the trained model
    joblib.dump(model, os.path.join(BASE_DIR, "feedback_model.joblib"))
    print("[train_from_feedback] ✅ Model saved to feedback_model.joblib")

if __name__ == "__main__":
    main()
