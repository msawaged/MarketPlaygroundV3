# backend/retrain_worker.py
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from joblib import dump
import time

CSV_PATH = "backend/feedback.csv"
MODEL_PATH = "backend/feedback_model.joblib"

def train_from_feedback():
    print("🔁 Starting model retraining from feedback.csv...")

    try:
        df = pd.read_csv(CSV_PATH)
        print(f"[train_from_feedback] ✅ Loaded {len(df)} feedback entries.")
    except Exception as e:
        print(f"[train_from_feedback] ❌ Failed to read CSV: {e}")
        return

    # ✅ Check for required columns
    if not {'strategy', 'label'}.issubset(df.columns):
        print("[train_from_feedback] ❌ Missing 'strategy' or 'label' column.")
        print(f"Columns found: {df.columns.tolist()}")
        return

    X = df["strategy"]
    y = df["label"]

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = LogisticRegression()
    model.fit(X_vec, y)

    dump((model, vectorizer), MODEL_PATH)
    print("[train_from_feedback] ✅ Model trained and saved.")

# Run once immediately
train_from_feedback()

# Optional: loop retrain every 30s (comment out if not needed)
# while True:
#     train_from_feedback()
#     time.sleep(30)
