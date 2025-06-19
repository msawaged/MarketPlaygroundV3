# train_from_feedback.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import joblib
import os

def main():
    print("🔁 Starting model retraining from feedback.csv...")

    # Load feedback data
    filepath = os.path.join(os.path.dirname(__file__), "feedback_data.json")
    if not os.path.exists(filepath):
        print("[train_from_feedback] ❌ feedback_data.json not found.")
        return

    try:
        df = pd.read_json(filepath)
        print(f"[train_from_feedback] ✅ Loaded {len(df)} feedback entries.")
    except Exception as e:
        print(f"[train_from_feedback] ❌ Failed to load feedback_data.json: {e}")
        return

    if "strategy" not in df.columns or "label" not in df.columns:
        print("[train_from_feedback] ❌ Missing 'strategy' or 'label' column.")
        return

    # Preprocess: turn strategy names into features
    X = df["strategy"]
    y = df["label"]

    if len(set(y)) < 2:
        print("[train_from_feedback] ⚠️ Not enough label classes to train. Need both 0 and 1.")
        return

    X_encoded = pd.get_dummies(X)

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X_encoded, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError as e:
        print(f"[train_from_feedback] ❌ train_test_split error: {e}")
        return

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    print("[train_from_feedback] ✅ Model trained.")

    # Evaluate and report accuracy
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"[train_from_feedback] 🧠 Model accuracy: {accuracy:.2f}")

    # Save model
    model_path = os.path.join(os.path.dirname(__file__), "feedback_model.joblib")
    joblib.dump(model, model_path)
    print(f"[train_from_feedback] 💾 Saved model to {model_path}")

if __name__ == "__main__":
    main()
