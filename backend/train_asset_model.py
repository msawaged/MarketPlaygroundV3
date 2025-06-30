# backend/train_asset_model.py

"""
Trains the asset class prediction model for MarketPlayground.
This ML model learns to predict asset classes (stocks, bonds, crypto, etc.)
based solely on user belief text.
"""

import os
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def train_asset_model():
    """
    Loads preprocessed training data and trains an asset class classifier.
    Saves both the trained pipeline and vectorizer to disk.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "training_data", "final_belief_asset_training.csv")

    print("📊 Loading training data for asset class model...")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"❌ Training data not found at {csv_path}")

    df = pd.read_csv(csv_path)

    if "belief" not in df.columns or "asset_class" not in df.columns:
        raise ValueError("❌ CSV must contain 'belief' and 'asset_class' columns.")

    X = df["belief"]
    y = df["asset_class"]

    print("🧠 Training asset class classifier...")

    # Split for evaluation
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Build pipeline with TF-IDF and logistic regression
    pipeline = Pipeline([
        ('vectorizer', TfidfVectorizer(max_features=300)),
        ('classifier', LogisticRegression(max_iter=500))
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    print("\n📈 Asset Class Classification Report:")
    print(classification_report(y_test, y_pred))

    # Save pipeline and components
    model_path = os.path.join(base_dir, "asset_class_model.joblib")
    vectorizer_path = os.path.join(base_dir, "asset_vectorizer.joblib")

    joblib.dump(pipeline, model_path)
    joblib.dump(pipeline.named_steps['vectorizer'], vectorizer_path)

    print(f"✅ Saved asset class model to {model_path}")
    print(f"✅ Saved vectorizer to {vectorizer_path}")

if __name__ == "__main__":
    train_asset_model()
