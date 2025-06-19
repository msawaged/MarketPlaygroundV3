# train_model.py
# Handles training for all models used in the AI engine

import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ✅ Function to train the belief model
def train_belief_model():
    df = pd.read_csv("feedback.csv")
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(df["belief"])
    y = df["label"]

    model = LogisticRegression()
    model.fit(X, y)

    joblib.dump(model, "feedback_model.joblib")
    joblib.dump(vectorizer, "vectorizer.joblib")
    print("✅ Belief model and vectorizer trained and saved.")

# ✅ Function to train feedback model (alias to belief model for compatibility)
def train_feedback_model():
    train_belief_model()
