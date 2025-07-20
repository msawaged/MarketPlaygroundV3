# backend/ai_engine/strategy_training_pipeline.py

"""
📈 Strategy Training Pipeline
Ingests user feedback to improve the ML strategy model. Enables auto-learning.
"""

import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

# Paths for training and saving
TRAINING_CSV = os.path.join("backend", "training_data", "cleaned_strategies.csv")
MODEL_PATH = os.path.join("backend", "multi_strategy_model.joblib")
VEC_PATH = os.path.join("backend", "multi_vectorizer.joblib")

def load_training_data():
    """
    Load training data from CSV.
    Returns: DataFrame with 'belief' and 'strategy' columns
    """
    return pd.read_csv(TRAINING_CSV)

def train_strategy_model():
    """
    Trains a strategy prediction model using beliefs + strategies.
    Saves the model and vectorizer to disk.
    """
    df = load_training_data()

    if 'belief' not in df or 'strategy' not in df:
        raise ValueError("Training CSV must include 'belief' and 'strategy' columns.")

    X = df['belief']
    y = df['strategy']

    vectorizer = TfidfVectorizer(max_features=5000)
    X_vec = vectorizer.fit_transform(X)

    model = RandomForestClassifier(n_estimators=150, random_state=42)
    model.fit(X_vec, y)

    # Save both artifacts
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VEC_PATH)
    print("✅ Strategy model retrained and saved.")

def run_training_pipeline():
    """
    Runs the full training pipeline.
    Can be called by retrain_worker, cron job, or debug endpoint.
    """
    try:
        train_strategy_model()
    except Exception as e:
        print(f"❌ Training failed: {e}")
