# backend/ai_engine/strategy_training_pipeline.py

"""
This script trains a simple ML model that maps (belief + metadata) text to strategy types.
It saves a vectorizer and classifier to be used in real-time strategy generation fallback.
"""

import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# === Define paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "..", "strategy_outcomes.csv")
MODEL_FILE = os.path.join(BASE_DIR, "multi_strategy_model.joblib")
VECTORIZER_FILE = os.path.join(BASE_DIR, "multi_vectorizer.joblib")

print("🔄 [1] Loading strategy data...")
if not os.path.exists(CSV_FILE):
    raise FileNotFoundError(f"❌ strategy_outcomes.csv not found at: {CSV_FILE}")

df = pd.read_csv(CSV_FILE)

# === Basic Validation ===
if "belief" not in df.columns or "strategy" not in df.columns:
    raise ValueError("❌ CSV must contain 'belief' and 'strategy' columns.")

df = df.dropna(subset=["belief", "strategy"])
print(f"✅ Loaded {len(df)} valid rows from CSV")

# === Preprocess input ===
df["input_text"] = df["belief"]  # You can concatenate more fields later if needed
X = df["input_text"]
y = df["strategy"]

# === Train/test split ===
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# === Build pipeline ===
pipeline = Pipeline([
    ("vectorizer", TfidfVectorizer()),
    ("classifier", RandomForestClassifier(n_estimators=100, random_state=42))
])

print("🧠 [2] Training strategy model...")
pipeline.fit(X_train, y_train)

# === Evaluate ===
y_pred = pipeline.predict(X_test)
print("\n📊 [3] Classification Report:")
print(classification_report(y_test, y_pred))

# === Save components ===
print("💾 [4] Saving model files...")
vectorizer = pipeline.named_steps["vectorizer"]
classifier = pipeline.named_steps["classifier"]

joblib.dump({"vectorizer": vectorizer, "classifier": classifier}, MODEL_FILE)
joblib.dump(vectorizer, VECTORIZER_FILE)

print(f"✅ Model saved to: {MODEL_FILE}")
print(f"✅ Vectorizer saved to: {VECTORIZER_FILE}")
