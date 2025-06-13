# belief_model.py
# Loads trained ML model and predicts tags from belief text

import joblib

# Load vectorizer and model
vectorizer = joblib.load("belief_vectorizer.joblib")
model = joblib.load("belief_model.joblib")

def predict_tags(belief_text):
    """
    Predicts direction, duration, and volatility from natural-language belief.
    
    Args:
        belief_text (str): Market belief statement
    
    Returns:
        dict: Predicted tags (direction, duration, volatility)
    """
    X = vectorizer.transform([belief_text])
    predictions = model.predict(X)[0]

    return {
        "direction": predictions[0],
        "duration": predictions[1],
        "volatility": predictions[2],
    }
