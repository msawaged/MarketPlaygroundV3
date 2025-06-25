# backend/train_multi_asset_model.py

"""
Trains a multi-asset classifier using 'cleaned_belief' → 'asset_class' labels
from the training dataset. Saves the trained model and vectorizer to disk
for use in belief parsing.
"""

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
import os

def train_multi_asset_model():
    """
    Loads data from training CSV, trains model to predict asset class
    from cleaned beliefs, and saves the model/vectorizer to backend/.
    """
    # === Step 1: Load the correct dataset ===
    csv_path = "backend/training_data/Training_Strategies.csv"
    df = pd.read_csv(csv_path)

    if "cleaned_belief" not in df.columns or "asset_class" not in df.columns:
        raise ValueError("Training_Strategies.csv must contain 'cleaned_belief' and 'asset_class' columns.")

    # === Step 2: Prepare features and labels ===
    X = df["cleaned_belief"].astype(str)
    y = df["asset_class"].astype(str)

    # === Step 3: Vectorize belief text ===
    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    # === Step 4: Train the model ===
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_vec, y)

    # === Step 5: Save model and vectorizer ===
    joblib.dump(model, "backend/multi_asset_model.joblib")
    joblib.dump(vectorizer, "backend/multi_vectorizer.joblib")
    print("✅ Multi-asset model trained and saved to backend/")

# === Run standalone if executed directly ===
if __name__ == "__main__":
    train_multi_asset_model()
