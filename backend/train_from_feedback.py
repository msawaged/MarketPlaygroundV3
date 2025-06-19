# train_from_feedback.py
# Handles model retraining from logged feedback stored in feedback.csv

import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

def train_from_feedback():
    """
    Trains a feedback classifier using feedback.csv.
    Safely handles dynamic file path resolution across local and cloud environments.
    """
    try:
        # 🔍 Get the absolute path to this script
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # ✅ Locate feedback.csv relative to this script
        csv_path = os.path.join(base_dir, 'feedback.csv')

        print(f"[train_from_feedback] 📄 Attempting to load CSV at: {csv_path}")

        # 📥 Load feedback data
        df = pd.read_csv(csv_path)

        # ✅ Make sure required columns exist
        if 'belief' not in df.columns or 'label' not in df.columns:
            raise ValueError("CSV must contain 'belief' and 'label' columns.")

        # 🎯 Extract inputs and labels
        X = df['belief']
        y = df['label']

        # 🔧 Convert text to features
        vectorizer = TfidfVectorizer()
        X_vec = vectorizer.fit_transform(X)

        # 🧠 Train classifier
        clf = LogisticRegression()
        clf.fit(X_vec, y)

        # 💾 Save model and vectorizer
        joblib.dump((vectorizer, clf), os.path.join(base_dir, 'feedback_model.joblib'))

        print(f"[train_from_feedback] ✅ Model retrained on {len(df)} entries and saved to feedback_model.joblib")

    except Exception as e:
        print(f"[train_from_feedback] ❌ Failed to read or train from feedback.csv: {e}")
