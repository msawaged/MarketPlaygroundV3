# backend/background_tasks.py

import asyncio
import json
import os
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

FEEDBACK_FILE = "backend/feedback_data.json"
MODEL_PATH = "backend/feedback_model.joblib"

async def background_retrain_loop(interval_seconds=300):
    """
    Background loop to retrain feedback model every `interval_seconds`.
    """
    while True:
        print("[background_tasks] 🔁 Checking for new feedback to retrain model...")
        try:
            if not os.path.exists(FEEDBACK_FILE):
                print("[background_tasks] ❌ No feedback file found. Skipping.")
            else:
                with open(FEEDBACK_FILE, "r") as f:
                    feedback_entries = json.load(f)

                texts = [
                    f"{entry['belief']} | {entry['strategy']['description']}"
                    for entry in feedback_entries
                ]
                labels = [entry["feedback"] for entry in feedback_entries]

                if len(set(labels)) < 2:
                    print("[background_tasks] ⚠️ Need at least 2 feedback types. Skipping.")
                elif len(labels) < 3:
                    print("[background_tasks] ⚠️ Not enough samples to retrain. Skipping.")
                else:
                    model = Pipeline([
                        ("tfidf", TfidfVectorizer()),
                        ("clf", LogisticRegression())
                    ])
                    model.fit(texts, labels)
                    joblib.dump(model, MODEL_PATH)
                    print("[background_tasks] ✅ Model retrained and saved.")

        except Exception as e:
            print(f"[background_tasks] ❌ Error in retraining: {e}")

        await asyncio.sleep(interval_seconds)
