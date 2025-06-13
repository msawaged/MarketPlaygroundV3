# belief_model_utils.py

from joblib import load
import os

# Paths to trained models
BASE_DIR = os.path.dirname(__file__)
VECTORIZER_PATH = os.path.join(BASE_DIR, "belief_vectorizer.joblib")
MODEL_PATH = os.path.join(BASE_DIR, "belief_model.joblib")

# Load once
vectorizer = load(VECTORIZER_PATH)
model = load(MODEL_PATH)

def classify_belief_with_model(belief_text):
    """
    Use trained ML model to classify belief into direction, duration, volatility.
    Returns: dict with 3 tags.
    """
    X = vectorizer.transform([belief_text])
    prediction = model.predict(X)[0]  # Output is a list of 3 labels
    return {
        "direction": prediction[0],
        "duration": prediction[1],
        "volatility": prediction[2]
    }
