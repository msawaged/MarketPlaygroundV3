import os
import json
import joblib
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer

# === Define paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")
MODEL_FILE = os.path.join(BASE_DIR, "feedback_model.joblib")

# === Load model if available ===
def load_feedback_model():
    if os.path.exists(MODEL_FILE):
        print("✅ Loading feedback model...")
        return joblib.load(MODEL_FILE)
    else:
        print("⚠️ No trained feedback model found.")
        return None

model = load_feedback_model()

# === Predict feedback label from belief + strategy ===
def predict_feedback_label(belief: str, strategy: str) -> str:
    if not model:
        return "unknown"
    text = f"{belief} => {strategy}"
    vectorizer = model["vectorizer"]
    clf = model["classifier"]
    X = vectorizer.transform([text])
    prediction = clf.predict(X)[0]
    return "good" if prediction == 1 else "bad"

# === Save feedback to JSON file ===
def save_feedback(belief: str, strategy: str, feedback: str = None, user_id: str = "anonymous"):
    data = []

    # Load existing data
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON decode error — starting fresh.")

    # Predict feedback if not provided
    if not feedback:
        feedback = predict_feedback_label(belief, strategy)

    # Build feedback entry
    feedback_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy,
        "result": feedback
    }

    # Append + save
    data.append(feedback_entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Feedback saved to file for user: {user_id}")

# === Compatibility function for older modules ===
def save_feedback_entry(belief: str, strategy: str, result: str, user_id: str = "anonymous"):
    """Alias for external use (e.g. from strategy_router)"""
    save_feedback(belief, strategy, feedback=result, user_id=user_id)
