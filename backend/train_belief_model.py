# backend/train_belief_model.py

"""
Trains a model to classify belief text into general strategy tags (e.g. 'income', 'growth').
Uses TF-IDF vectorization and Logistic Regression classifier.

Supports both:
- Direct CLI use (loads default CSV and saves to backend/)
- Programmatic use with custom input/output paths (used by training pipelines)
"""

import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report


def train_belief_model(
    input_file: str = None,
    model_output_path: str = None,
    vectorizer_output_path: str = None
):
    """
    Train belief tag classification model and save it to disk.

    Args:
        input_file (str): Path to CSV with 'belief' and 'tag' columns
        model_output_path (str): Directory to save model (.joblib)
        vectorizer_output_path (str): Directory to save vectorizer (.joblib)
    """

    # === Fallback to default paths if not specified ===
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    input_file = input_file or os.path.join(BASE_DIR, "training_data", "clean_belief_tags.csv")
    model_output_path = model_output_path or BASE_DIR
    vectorizer_output_path = vectorizer_output_path or BASE_DIR

    MODEL_PATH = os.path.join(model_output_path, "belief_model.joblib")
    VECTORIZER_PATH = os.path.join(vectorizer_output_path, "belief_vectorizer.joblib")

    # === Load and verify training data ===
    df = pd.read_csv(input_file)
    if "belief" not in df.columns or "tag" not in df.columns:
        raise ValueError("CSV must contain 'belief' and 'tag' columns")

    df = df.dropna(subset=["belief", "tag"])
    if df.empty:
        print("❌ No valid training data found in belief tag file.")
        return

    # === Prepare inputs ===
    X = df["belief"]
    y = df["tag"].astype(str).str.lower()

    # === TF-IDF vectorization ===
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=3000)
    X_vec = vectorizer.fit_transform(X)

    # === Train classifier ===
    model = LogisticRegression(max_iter=1000)
    model.fit(X_vec, y)

    # === Evaluation ===
    X_train, X_test, y_train, y_test = train_test_split(X_vec, y, test_size=0.2, random_state=42)
    preds = model.predict(X_test)

    print("🧠 Belief Classifier Accuracy Report:\n")
    print(classification_report(y_test, preds))

    # === Save model and vectorizer ===
    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"✅ Model saved to → {MODEL_PATH}")
    print(f"✅ Vectorizer saved to → {VECTORIZER_PATH}")


# === CLI Entrypoint ===
if __name__ == "__main__":
    train_belief_model()
