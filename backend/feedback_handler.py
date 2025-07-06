# backend/feedback_handler.py

import os
import json
import joblib
from datetime import datetime

# === File Paths ===
# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# JSON file where all user feedback entries are stored
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")

# Serialized ML model file for feedback prediction
MODEL_FILE = os.path.join(BASE_DIR, "feedback_model.joblib")

def load_feedback_model():
    """
    Loads the trained feedback ML model if it exists.
    Returns None if model file not found.
    """
    if os.path.exists(MODEL_FILE):
        print("✅ Loading feedback model...")
        return joblib.load(MODEL_FILE)
    else:
        print("⚠️ No trained feedback model found.")
        return None

# Load model once at import time to reuse
model = load_feedback_model()

def predict_feedback_label(belief: str, strategy: str) -> str:
    """
    Predicts feedback label ('good' or 'bad') based on
    combined belief and strategy text using the loaded ML model.

    Returns 'unknown' if no model is loaded.
    """
    if not model:
        return "unknown"
    
    # Combine belief and strategy for prediction input
    text = f"{belief} => {strategy}"
    
    # Extract vectorizer and classifier from the loaded model
    vectorizer = model["vectorizer"]
    clf = model["classifier"]
    
    # Transform text input and predict
    X = vectorizer.transform([text])
    prediction = clf.predict(X)[0]
    
    return "good" if prediction == 1 else "bad"

def save_feedback(belief: str, strategy: str, feedback: str = None, user_id: str = "anonymous"):
    """
    Saves user feedback to the feedback JSON file.
    If feedback is not provided, predicts it using the ML model.

    The feedback entry includes timestamp, user_id, belief, strategy, and result.
    """
    data = []

    # Load existing feedback entries if the file exists
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON decode error — starting fresh.")
                data = []

    # If feedback not explicitly provided, infer it via prediction
    if not feedback:
        feedback = predict_feedback_label(belief, strategy)

    # Construct feedback entry
    feedback_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy,
        "result": feedback
    }

    # Append new entry and save back to JSON file
    data.append(feedback_entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Feedback saved to file for user: {user_id}")

def save_feedback_entry(belief: str, strategy: str, result: str, user_id: str = "anonymous"):
    """
    Alias function for compatibility with older code.
    Allows external modules (e.g., strategy_router) to save feedback easily.
    """
    save_feedback(belief, strategy, feedback=result, user_id=user_id)
