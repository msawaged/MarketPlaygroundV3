# backend/train_model.py

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import os

def train_model_from_feedback(csv_path="backend/feedback.csv"):
    """
    Trains a logistic regression model from labeled strategy feedback.

    Parameters:
        csv_path (str): Path to the CSV file containing 'strategy' and 'label' columns.

    Returns:
        None. Saves updated model and vectorizer to disk.
    """
    print(f"[train_model_from_feedback] 📂 Reading feedback data from: {csv_path}")
    
    try:
        df = pd.read_csv(csv_path)

        # Sanity check
        if df.empty or 'strategy' not in df.columns or 'label' not in df.columns:
            print("[train_model_from_feedback] ❌ Invalid or empty CSV structure.")
            return

        print(f"[train_model_from_feedback] 📊 Loaded {len(df)} feedback records. Starting training...")

        # Vectorize strategy text
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform(df['strategy'])
        y = df['label']

        # Train logistic regression model
        model = LogisticRegression()
        model.fit(X, y)

        # Save updated model + vectorizer
        joblib.dump(model, os.path.join("backend", "feedback_model.joblib"))
        joblib.dump(vectorizer, os.path.join("backend", "vectorizer.joblib"))

        print("[train_model_from_feedback] ✅ Feedback model updated successfully.")

    except FileNotFoundError:
        print(f"[train_model_from_feedback] ❌ CSV file not found: {csv_path}")
    except Exception as e:
        print(f"[train_model_from_feedback] ❌ Unexpected error: {e}")
