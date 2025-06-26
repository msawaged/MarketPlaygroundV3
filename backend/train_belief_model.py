# backend/train_belief_model.py

"""
Train belief classifier model to map user beliefs to high-level tags.
This model helps predict intent (e.g. 'income', 'growth') based on natural-language beliefs.
"""

import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

def train_belief_model(input_file, model_output_path, vectorizer_output_path):
    # Load training data
    df = pd.read_csv(input_file)

    # Verify required columns
    if 'belief' not in df.columns or 'tags' not in df.columns:
        raise ValueError("CSV must contain 'belief' and 'tags' columns")

    # Clean and normalize tags (take first tag only)
    df['tag'] = df['tags'].astype(str).apply(lambda x: x.split(',')[0].strip().lower())

    # Prepare features and labels
    X = df['belief']
    y = df['tag']

    # Vectorize belief text
    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    # Train classifier
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_vec, y)

    # Save model and vectorizer to output paths
    model_path = os.path.join(model_output_path, "belief_model.joblib")
    vectorizer_path = os.path.join(vectorizer_output_path, "belief_vectorizer.joblib")
    joblib.dump(clf, model_path)
    joblib.dump(vectorizer, vectorizer_path)

    print(f"✅ Belief model saved to: {model_path}")
    print(f"✅ Vectorizer saved to: {vectorizer_path}")

if __name__ == "__main__":
    # Test run (optional)
    train_belief_model(
        input_file="backend/training_data/clean_belief_tags.csv",
        model_output_path="backend",
        vectorizer_output_path="backend"
    )
