# backend/train_model.py

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import os

# 🔧 File paths
DATA_FILE = "backend/historic_data.csv"
MODEL_FILE = "backend/best_model.joblib"
VECTORIZER_FILE = "backend/belief_vectorizer.joblib"

def main():
    print("[train_model.py] Loading data...")

    # 📥 Load CSV
    df = pd.read_csv(DATA_FILE)

    # 🧹 Drop any rows missing belief or P&L
    df = df.dropna(subset=["belief", "realizedPL"])

    print(f"[train_model.py] Training rows: {len(df)}")

    # ✂️ Split data
    X_train, X_test, y_train, y_test = train_test_split(
        df["belief"], df["realizedPL"], test_size=0.1, random_state=42
    )

    # 🔠 Text vectorization
    vectorizer = TfidfVectorizer()
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # 🤖 Train regression model
    model = LinearRegression()
    model.fit(X_train_vec, y_train)

    # 📈 Evaluate
    y_pred = model.predict(X_test_vec)
    score = r2_score(y_test, y_pred)
    print(f"[train_model.py] R^2 on test set: {score:.4f}")

    # 💾 Save model + vectorizer
    joblib.dump(model, MODEL_FILE)
    joblib.dump(vectorizer, VECTORIZER_FILE)
    print(f"[train_model.py] Model saved to {MODEL_FILE}")
    print(f"[train_model.py] Vectorizer saved to {VECTORIZER_FILE}")

if __name__ == "__main__":
    main()
