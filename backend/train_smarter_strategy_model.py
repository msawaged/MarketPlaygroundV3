# backend/train_smarter_strategy_model.py

"""
Trains a smarter strategy model using belief + metadata:
- Inputs: dict-style rows (belief, ticker, direction, confidence, asset_class)
- Output: strategy (e.g. 'bull call spread')
- Model is saved as a full sklearn Pipeline using DictVectorizer
"""

import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os

# === File Paths ===
DATA_PATH = "backend/Training_Strategies_Enhanced.csv"
PIPELINE_PATH = "backend/smart_strategy_pipeline.joblib"

def train_strategy_model():
    """Main training entry point expected by train_all_models.py"""
    # Load and clean data
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=['belief', 'strategy'])

    # Convert to list of dicts for DictVectorizer
    X = df[['belief', 'ticker', 'direction', 'confidence', 'asset_class']].to_dict(orient="records")
    y = df['strategy']

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Define Pipeline with DictVectorizer and RandomForest
    pipeline = Pipeline([
        ('vectorizer', DictVectorizer(sparse=True)),
        ('clf', RandomForestClassifier(n_estimators=150, random_state=42))
    ])

    # Fit pipeline
    pipeline.fit(X_train, y_train)

    # Save full pipeline
    joblib.dump(pipeline, PIPELINE_PATH)
    print(f"✅ Model saved to {PIPELINE_PATH}")

    # Evaluate accuracy
    score = pipeline.score(X_test, y_test)
    print(f"🎯 Accuracy on test set: {score:.2f}")

if __name__ == "__main__":
    train_strategy_model()
