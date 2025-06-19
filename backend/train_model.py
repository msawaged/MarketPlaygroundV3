# train_model.py

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

def train_belief_model():
    """
    Train a logistic regression model on belief text to classify tags.
    Saves model as 'feedback_model.joblib' and vectorizer as 'vectorizer.joblib'
    """
    df = pd.read_csv("feedback.csv")
    if 'belief' not in df.columns or 'label' not in df.columns:
        raise ValueError("CSV must contain 'belief' and 'label' columns.")

    X = df["belief"]
    y = df["label"]

    vectorizer = TfidfVectorizer()
    X_vectorized = vectorizer.fit_transform(X)

    model = LogisticRegression()
    model.fit(X_vectorized, y)

    joblib.dump(model, "feedback_model.joblib")
    joblib.dump(vectorizer, "vectorizer.joblib")
    print("✅ Belief model and vectorizer retrained and saved.")

# Optional CLI test runner
if __name__ == "__main__":
    train_belief_model()
