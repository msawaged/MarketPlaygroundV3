# tag_classifier.py

import joblib

# Load the trained tag classification model
model = joblib.load("belief_tag_classifier.joblib")

def classify_tag(belief):
    """
    Takes in natural language belief and returns a predicted tag.
    Example tags: 'bullish', 'bearish', 'longterm', 'shortterm', 'highvol', etc.
    """
    return model.predict([belief])[0]

# Example:
if __name__ == "__main__":
    print(classify_tag("AI will outperform for years"))
