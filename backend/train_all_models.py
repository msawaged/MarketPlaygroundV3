# backend/train_all_models.py

"""
This script runs the full training pipeline for all ML models used in MarketPlayground:
1. Belief Tag Classifier
2. Asset Class (Strategy Type) Predictor
3. Feedback Quality Classifier (Good vs Bad)
4. Strategy Type Classifier (from feedback history)
"""

import os

# ✅ Use relative imports for safe module execution
from .train_belief_model import train_belief_model
from .train_smarter_strategy_model import train_strategy_model
from .feedback_trainer import train_feedback_model, train_strategy_classifier_from_feedback

def train_all_models():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    belief_input = os.path.join(base_dir, "training_data", "clean_belief_tags.csv")

    print("\n✅ Starting full training pipeline...\n")

    # === Step 1: Train Belief Tag Classifier ===
    train_belief_model(
        input_file=belief_input,
        model_output_path=base_dir,
        vectorizer_output_path=base_dir
    )

    # === Step 2: Train Multi-Feature Strategy Model ===
    train_strategy_model()  # No arguments needed — internally loads CSV

    # === Step 3: Train Feedback Classifier (good vs bad) ===
    train_feedback_model()

    # === Step 4: Train Strategy Type Classifier (from feedback history) ===
    train_strategy_classifier_from_feedback()

    print("\n✅ All models retrained and saved.")

if __name__ == "__main__":
    train_all_models()
