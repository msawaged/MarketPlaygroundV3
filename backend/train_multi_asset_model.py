# backend/train_multi_asset_model.py

"""
Trains a strategy model using user beliefs and strategy metadata.
Uses RandomForestClassifier for improved performance.
"""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

# === Load your training data ===
csv_path = os.path.join("backend", "Training_Strategies.csv")
df = pd.read_csv(csv_path)

# === Basic validation ===
required_columns = {"belief", "ticker", "asset_class", "direction", "strategy"}
if not required_columns.issubset(set(df.columns)):
    raise ValueError(f"Missing required columns in CSV: {required_columns - set(df.columns)}")

# === Combine text features ===
df["input_text"] = df["belief"] + " | " + df["ticker"] + " | " + df["asset_class"] + " | " + df["direction"]

# === Split into train/test ===
X = df["input_text"]
y = df["strategy"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# === Create model pipeline ===
pipeline = make_pipeline(
    TfidfVectorizer(),
    RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42)
)

# === Train the model ===
pipeline.fit(X_train, y_train)

# === Evaluate ===
y_pred = pipeline.predict(X_test)
print("\n📊 Strategy Model Evaluation:")
print(classification_report(y_test, y_pred))

# === Save model + vectorizer ===
joblib.dump(pipeline.named_steps["randomforestclassifier"], "backend/multi_strategy_model.joblib")
joblib.dump(pipeline.named_steps["tfidfvectorizer"], "backend/multi_vectorizer.joblib")

print("✅ Model and vectorizer saved.")
