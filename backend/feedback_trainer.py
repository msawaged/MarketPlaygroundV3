# feedback_trainer.py
# ✅ This module reads user feedback and retrains all relevant models

import os
import pandas as pd
from joblib import dump
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ✅ This function is imported by retrain_worker.py and run on startup
def train_from_feedback():
    print("🔁 Starting model retraining from feedback.csv...")

    # 🔍 Detect full path to feedback.csv relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "feedback.csv")
    print(f"📂 Reading feedback data from: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[train_from_feedback] ❌ Failed to read CSV: {e}")
        return

    required_cols = {"belief", "label"}
    if not required_cols.issubset(df.columns):
        print(f"[train_from_feedback] ❌ Missing required columns: {required_cols - set(df.columns)}")
        return

    # 🧠 Vectorize beliefs
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(df["belief"])
    y = df["label"]

    # 🏋️ Train simple logistic model
    model = LogisticRegression()
    model.fit(X, y)

    # 💾 Save updated model and vectorizer
    dump(model, os.path.join(base_dir, "feedback_model.joblib"))
    dump(vectorizer, os.path.join(base_dir, "vectorizer.joblib"))

    print("✅ Retraining complete.")
