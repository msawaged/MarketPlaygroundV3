# feedback_trainer.py
# ✅ Handles retraining of models based on feedback.csv

import os
import pandas as pd
from joblib import dump
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ✅ Accepts a custom path to the feedback CSV
def train_from_feedback(feedback_path):
    print("🔁 Starting model retraining from feedback.csv...")
    print(f"📂 Reading feedback data from: {feedback_path}")

    try:
        df = pd.read_csv(feedback_path)
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

    # 🏋️ Train model
    model = LogisticRegression()
    model.fit(X, y)

    # 💾 Save updated files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dump(model, os.path.join(base_dir, "feedback_model.joblib"))
    dump(vectorizer, os.path.join(base_dir, "vectorizer.joblib"))

    print("✅ Retraining complete.")
