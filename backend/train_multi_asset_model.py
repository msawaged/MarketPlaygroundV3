# backend/train_multi_asset_model.py

"""
This trains a classification model to predict asset_class from belief text.
Saves both the model and the vectorizer as joblib files.
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import os

def train_strategy_model(input_file: str, model_output_path: str, vectorizer_output_path: str):
    # Load and validate data
    df = pd.read_csv(input_file)
    expected_cols = ['belief', 'asset_class']
    actual_cols = list(df.columns)
    print(f"🚨 Columns found: {actual_cols}")

    if not all(col in actual_cols for col in expected_cols):
        raise ValueError("CSV must contain 'belief' and 'asset_class' columns")

    # Filter down to the required columns
    df = df[['belief', 'asset_class']].dropna()

    # Features and labels
    X = df['belief'].astype(str)
    y = df['asset_class'].astype(str).str.lower()  # Ensure consistency

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Pipeline: vectorizer + classifier
    pipeline = Pipeline([
        ('vectorizer', TfidfVectorizer(stop_words='english')),
        ('classifier', LogisticRegression(max_iter=1000))
    ])

    # Fit the pipeline
    pipeline.fit(X_train, y_train)
    accuracy = pipeline.score(X_test, y_test)
    print(f"✅ Trained LogisticRegression model (accuracy: {accuracy:.2f})")

    # Save pipeline components
    model_path = os.path.join(model_output_path, "multi_asset_model.joblib")
    vectorizer_path = os.path.join(vectorizer_output_path, "multi_vectorizer.joblib")

    joblib.dump(pipeline.named_steps['classifier'], model_path)
    joblib.dump(pipeline.named_steps['vectorizer'], vectorizer_path)

    print(f"✅ Saved model to {model_path}")
    print(f"✅ Saved vectorizer to {vectorizer_path}")
