# backend/train_all_models.py

"""
This script retrains ALL major models in the backend:
- Belief model
- Multi-asset and strategy models
- Feedback model
"""

import os
from train_model import train_belief_model
from train_multi_asset_model import train_asset_and_strategy_model
from train_model import train_feedback_model


def train_all_models():
    print("🧠 Starting full model retraining pipeline...")

    # Get backend path dynamically for both local and cloud
    base_path = os.path.dirname(os.path.abspath(__file__))

    # Belief Model
    try:
        belief_path = os.path.join(base_path, "belief_model.joblib")
        vectorizer_path = os.path.join(base_path, "vectorizer.joblib")
        train_belief_model(belief_path, vectorizer_path)
        print("✅ Belief model retrained.")
    except Exception as e:
        print(f"❌ Failed to retrain belief model: {e}")

    # Multi-Asset + Multi-Strategy Models
    try:
        asset_model_path = os.path.join(base_path, "multi_asset_model.joblib")
        strategy_model_path = os.path.join(base_path, "multi_strategy_model.joblib")
        vectorizer_path = os.path.join(base_path, "multi_vectorizer.joblib")
        train_asset_and_strategy_model(asset_model_path, strategy_model_path, vectorizer_path)
        print("✅ Asset + Strategy models retrained.")
    except Exception as e:
        print(f"❌ Failed to retrain asset/strategy models: {e}")

    # Feedback Model
    try:
        feedback_path = os.path.join(base_path, "feedback.csv")
        model_path = os.path.join(base_path, "feedback_model.joblib")
        train_feedback_model(feedback_path, model_path)
        print("✅ Feedback model retrained.")
    except Exception as e:
        print(f"❌ Failed to retrain feedback model: {e}")

    print("🚀 Full model retraining complete.")
